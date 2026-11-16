"""Explicit local CPU paired comparison. Does not change application defaults."""
import argparse
from datetime import datetime, timezone
import hashlib
import http.client
import json
import os
from pathlib import Path
import socket
import subprocess
import time

from mechanics import SpanSelector, LocalGenerator, make_payload

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def sha(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def memory_telemetry(pid):
    try:
        value = Path(f'/proc/{pid}/status').read_text()
        return {'status': 'observed', 'lines': [s for s in value.splitlines() if s.startswith(('VmHWM:', 'VmRSS:'))]}
    except OSError as exc:
        return {'status': 'unavailable', 'reason': type(exc).__name__}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--assets', type=Path, default=Path('/tmp/rag-local-assets'))
    parser.add_argument('--output', type=Path, default=REPO / 'build/numbered-spans-v1-run-001')
    args = parser.parse_args()
    out = args.output.resolve()
    if not out.is_relative_to(REPO / 'build'):
        raise ValueError('output must be a new directory under repository build/')
    out.mkdir(parents=True, exist_ok=False)
    fixture = json.loads((HERE / 'cases.json').read_text())
    lock = json.loads((HERE / 'cases.lock.json').read_text())
    if lock['status'] != 'frozen_before_execution' or sha(HERE / 'cases.json') != lock['cases_sha256']:
        raise ValueError('fixture has not been frozen or changed')
    for name, expected in lock['implementation_sha256'].items():
        if sha(REPO / name) != expected:
            raise ValueError('implementation changed after freezing: ' + name)
    for span in fixture['offered_spans']:
        source = REPO / span['source_path']
        if sha(source) != span['source_sha256'] or source.read_text()[span['char_start']:span['char_end']] != span['text']:
            raise ValueError('span provenance changed')
    sources = json.loads((REPO / 'experiments/local-generation-smoke/sources.json').read_text())
    model = args.assets / sources['model']['filename']
    binary = args.assets / sources['runtime']['server_path']
    if sha(model) != sources['model']['expected_sha256'] or sha(binary) != sources['runtime']['server_sha256']:
        raise ValueError('model/runtime checksum mismatch')
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    flags = ['--model', str(model.resolve()), '--alias', 'local-model', '--host', '127.0.0.1', '--port', str(port),
             '--ctx-size', '4096', '--threads', '4', '--threads-batch', '4', '--parallel', '1', '--gpu-layers', '0',
             '--no-agent', '--no-webui', '--no-ui-mcp-proxy', '--reasoning', 'off',
             '--chat-template-kwargs', '{"enable_thinking":false}']
    env = {k: v for k, v in os.environ.items()
           if not k.startswith('LLAMA_') and k not in {'HF_TOKEN', 'HUGGING_FACE_HUB_TOKEN'}}
    for key, name in [('HOME', 'home'), ('XDG_CACHE_HOME', 'cache')]:
        folder = out / name
        folder.mkdir()
        env[key] = str(folder)
    env['HF_HUB_OFFLINE'] = '1'
    manifest = {'schema_version': 1, 'started_utc': datetime.now(timezone.utc).isoformat(),
                'cases_sha256': lock['cases_sha256'], 'implementation_sha256': lock['implementation_sha256'],
                'model_sha256': sha(model), 'runtime_sha256': sha(binary),
                'server_flags': [model.name if x == str(model.resolve()) else '<ephemeral>' if x == str(port) else x for x in flags],
                'attempts': []}
    process = None
    start = time.monotonic()
    try:
        with (out / 'server.log').open('w') as log:
            process = subprocess.Popen([str(binary.resolve())] + flags, cwd=REPO, env=env, stdout=log, stderr=log)
            while time.monotonic() - start < 60:
                if process.poll() is not None:
                    raise RuntimeError('model server exited during startup')
                connection = http.client.HTTPConnection('127.0.0.1', port, timeout=1)
                try:
                    connection.request('GET', '/health')
                    response = connection.getresponse()
                    if response.status == 200 and json.loads(response.read()).get('status') == 'ok':
                        break
                except (OSError, http.client.HTTPException):
                    pass
                finally:
                    connection.close()
                time.sleep(0.2)
            else:
                raise TimeoutError('model server startup timeout')
            manifest['startup_seconds'] = time.monotonic() - start
            endpoint = f'http://127.0.0.1:{port}'
            selector, generator = SpanSelector(endpoint, 120), LocalGenerator(endpoint, 120)
            for case in fixture['cases']:
                for arm in case['arm_order']:
                    before = time.monotonic()
                    name = case['id'] + '--' + arm
                    payload = make_payload(case['query'], fixture['offered_spans'], arm)
                    write(out / (name + '.request.json'), payload)
                    selection = selector.select(case['query'], fixture['offered_spans'], arm)
                    result = {'case_id': case['id'], 'arm': arm, 'selector': selection,
                              'generator_invoked': selection['status'] == 'selected', 'generator': None}
                    if result['generator_invoked']:
                        result['generator'] = generator.generate(case['query'], selection['selected_context'])
                    write(out / (name + '.result.json'), result)
                    entry = {'case_id': case['id'], 'arm': arm, 'request_file': name + '.request.json',
                             'request_sha256': sha(out / (name + '.request.json')),
                             'result_file': name + '.result.json', 'result_sha256': sha(out / (name + '.result.json')),
                             'selector_status': selection['status'], 'selected_span_ids': selection['selected_span_ids'],
                             'generator_invoked': result['generator_invoked'],
                             'generator_status': result['generator']['status'] if result['generator'] else None,
                             'seconds': time.monotonic() - before}
                    manifest['attempts'].append(entry)
                    write(out / 'manifest.json', manifest)
                    print(json.dumps(entry, ensure_ascii=False), flush=True)
            manifest['telemetry'] = memory_telemetry(process.pid)
    except Exception as exc:
        manifest['execution_error'] = type(exc).__name__ + ': ' + str(exc)
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
        manifest['server_stopped'] = process is None or process.poll() is not None
        manifest['server_returncode'] = process.returncode if process else None
        manifest['finished_utc'] = datetime.now(timezone.utc).isoformat()
        write(out / 'manifest.json', manifest)
    print(json.dumps({'server_stopped': manifest['server_stopped'], 'error': manifest.get('execution_error')}), flush=True)
    return int(bool(manifest.get('execution_error')))


if __name__ == '__main__':
    raise SystemExit(main())
