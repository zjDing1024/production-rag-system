"""Explicit pinned CPU run, with incremental evidence preservation and process cleanup."""
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
from adapter import BranchedGenerator, run_case, expected_request
from preflight import preflight

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


def telemetry(pid):
    try:
        lines = Path(f'/proc/{pid}/status').read_text().splitlines()
        return {'status': 'observed', 'lines': [s for s in lines if s.startswith(('VmHWM:', 'VmRSS:'))]}
    except OSError as exc:
        return {'status': 'unavailable', 'reason': type(exc).__name__}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--assets', type=Path, default=Path('/tmp/rag-local-assets'))
    parser.add_argument('--output', type=Path, default=REPO / 'build/source-transfer-v1-run-001')
    args = parser.parse_args()
    out = args.output.resolve()
    if not out.is_relative_to(REPO / 'build'):
        raise ValueError('output must be a new directory under build/')
    out.mkdir(parents=True, exist_ok=False)
    fixture = json.loads((HERE / 'cases.json').read_text())
    lock = json.loads((HERE / 'cases.lock.json').read_text())
    if lock['status'] != 'frozen_before_execution' or sha(HERE / 'cases.json') != lock['cases_sha256']:
        raise ValueError('fixture not frozen or changed')
    for name, expected in lock['file_sha256'].items():
        if sha(REPO / name) != expected:
            raise ValueError('frozen file changed: ' + name)
    frozen_preflight = json.loads((HERE / 'preflight.json').read_text())
    if preflight() != frozen_preflight:
        raise ValueError('actual lexical/scope preflight changed')
    plans = {r['case_id']: r['plans'] for r in frozen_preflight['rows']}
    sources = json.loads((REPO / 'experiments/local-generation-smoke/sources.json').read_text())
    model, binary = args.assets / sources['model']['filename'], args.assets / sources['runtime']['server_path']
    if sha(model) != sources['model']['expected_sha256'] or sha(binary) != sources['runtime']['server_sha256']:
        raise ValueError('asset checksum mismatch')
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    flags = ['--model', str(model.resolve()), '--alias', 'local-model', '--host', '127.0.0.1', '--port', str(port),
             '--ctx-size', '4096', '--threads', '4', '--threads-batch', '4', '--parallel', '1', '--gpu-layers', '0',
             '--no-agent', '--no-webui', '--no-ui-mcp-proxy', '--reasoning', 'off',
             '--chat-template-kwargs', '{"enable_thinking":false}']
    env = {k: v for k, v in os.environ.items() if not k.startswith('LLAMA_') and k not in {'HF_TOKEN', 'HUGGING_FACE_HUB_TOKEN'}}
    for key, folder in [('HOME', 'home'), ('XDG_CACHE_HOME', 'cache')]:
        path = out / folder
        path.mkdir()
        env[key] = str(path)
    env['HF_HUB_OFFLINE'] = '1'
    manifest = {'schema_version': 1, 'started_utc': datetime.now(timezone.utc).isoformat(),
                'cases_sha256': lock['cases_sha256'], 'file_sha256': lock['file_sha256'],
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
                    raise RuntimeError('server exited during startup')
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
                raise TimeoutError('startup timeout')
            manifest['startup_seconds'] = time.monotonic() - start
            endpoint = f'http://127.0.0.1:{port}'
            generator = BranchedGenerator(endpoint, 120)
            for case in fixture['cases']:
                before = time.monotonic()
                name = case['id']
                query = case['request']['query']
                entry = {'case_id': name, 'result_file': name + '.result.json', 'complete': False}
                manifest['attempts'].append(entry)
                write(out / 'manifest.json', manifest)
                result = {'case_id': name, 'arms': {}}
                for arm in case['arm_order']:
                    generator.last_payload = None
                    outcome = run_case(case, arm, generator)
                    for key in ('context', 'preflight', 'ranking', 'index_sha256', 'catalog_sha256'):
                        if outcome[key] != plans[name][arm][key]:
                            raise ValueError('pipeline differs from frozen preflight: ' + key)
                    request = generator.last_payload
                    if outcome['generator_called'] and request != expected_request(query, outcome['context']):
                        raise ValueError('actual generation request differs from frozen adapter')
                    if not outcome['generator_called'] and request is not None:
                        raise ValueError('no-run unexpectedly called model')
                    result['arms'][arm] = {'request': request, 'outcome': outcome}
                    write(out / entry['result_file'], result)
                entry.update(complete=True, result_sha256=sha(out / entry['result_file']),
                             arm_order=list(result['arms']),
                             generator_calls=sum(v['outcome']['generator_called'] for v in result['arms'].values()),
                             seconds=time.monotonic() - before)
                write(out / 'manifest.json', manifest)
                print(json.dumps({'case_id': name, 'arms': {a: v['outcome']['status'] for a, v in result['arms'].items()}}), flush=True)
            manifest['telemetry'] = telemetry(process.pid)
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
        manifest.update(server_stopped=process is None or process.poll() is not None,
                        server_returncode=process.returncode if process else None,
                        finished_utc=datetime.now(timezone.utc).isoformat())
        write(out / 'manifest.json', manifest)
    print(json.dumps({'server_stopped': manifest['server_stopped'], 'error': manifest.get('execution_error')}), flush=True)
    return int(bool(manifest.get('execution_error')))


if __name__ == '__main__':
    raise SystemExit(main())
