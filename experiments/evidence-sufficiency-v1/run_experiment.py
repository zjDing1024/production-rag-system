"""Live paired gate off/on and same-question evidence-substitution diagnostic.

Only explicit invocation starts the pinned local CPU model. No retries or tuning.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import http.client
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / 'src'))


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def write(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--assets', type=Path, default=Path('/tmp/rag-local-assets'))
    parser.add_argument('--output', type=Path, default=REPO / 'build/evidence-sufficiency-v1-run-001')
    args = parser.parse_args()
    assets = args.assets.resolve()
    out = args.output.resolve()
    if not out.is_relative_to(REPO / 'build'):
        raise ValueError('output must stay under repository build/')
    out.mkdir(parents=True, exist_ok=False)
    fixture = json.loads((HERE / 'cases.json').read_text())
    lock = json.loads((HERE / 'cases.lock.json').read_text())
    if lock['status'] != 'frozen_before_execution' or sha(HERE / 'cases.json') != lock['cases_sha256']:
        raise ValueError('fixture is not frozen or was changed')
    for name, expected in fixture['code_sha256'].items():
        if sha(REPO / 'src/rag_foundation' / name) != expected:
            raise ValueError('code changed after protocol freeze: ' + name)
    sources = json.loads((HERE.parent / 'local-generation-smoke/sources.json').read_text())
    model = assets / sources['model']['filename']
    binary = assets / sources['runtime']['server_path']
    if sha(model) != sources['model']['expected_sha256'] or sha(binary) != sources['runtime']['server_sha256']:
        raise ValueError('model/runtime checksum mismatch')
    from rag_foundation.generation import GenerationPipeline
    from rag_foundation.sufficiency import LocalSufficiencyGate
    # Recheck retrieval before any model request, without injecting frozen gold.
    preview = GenerationPipeline(REPO)
    for case in fixture['cases']:
        if preview.retriever.retrieve({'query': case['query'], 'k': 3}) != case['retrieval']:
            raise ValueError('retrieval changed after manual evidence labeling: ' + case['id'])
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    endpoint = f'http://127.0.0.1:{port}'
    flags = ['--model', str(model), '--alias', 'local-model', '--host', '127.0.0.1', '--port', str(port),
             '--ctx-size', '4096', '--threads', '4', '--threads-batch', '4', '--parallel', '1',
             '--gpu-layers', '0', '--no-agent', '--no-webui', '--no-ui-mcp-proxy',
             '--reasoning', 'off', '--chat-template-kwargs', '{"enable_thinking":false}']
    env = {k: v for k, v in os.environ.items()
           if not k.startswith('LLAMA_') and k not in {'HF_TOKEN', 'HUGGING_FACE_HUB_TOKEN'}}
    for key, name in [('HOME', 'home'), ('XDG_CACHE_HOME', 'cache')]:
        path = out / name
        path.mkdir()
        env[key] = str(path)
    env['HF_HUB_OFFLINE'] = '1'
    manifest = {'schema_version': 1, 'started_utc': datetime.now(timezone.utc).isoformat(),
                'cases_sha256': lock['cases_sha256'], 'runner_sha256': sha(Path(__file__)),
                'model_sha256': sha(model), 'runtime_sha256': sha(binary),
                'source_sha256': fixture['code_sha256'], 'attempts': [],
                'server_flags': [model.name if x == str(model) else '<ephemeral>' if x == str(port) else x for x in flags]}
    process = None
    started = time.monotonic()
    try:
        with (out / 'server.log').open('w') as log:
            process = subprocess.Popen([str(binary)] + flags, cwd=REPO, env=env, stdout=log, stderr=log)
            while time.monotonic() - started < 60:
                if process.poll() is not None:
                    raise RuntimeError('server exited before ready')
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
                raise TimeoutError('startup exceeded 60 seconds')
            manifest['startup_seconds'] = time.monotonic() - started
            pipelines = {mode: GenerationPipeline(REPO, endpoint, timeout=120, evidence_gate=mode == 'on')
                         for mode in ('off', 'on')}
            for case in fixture['cases']:
                for mode in fixture['plan']['gate_conditions']:
                    before = time.monotonic()
                    pipeline = pipelines[mode]
                    invoked = []
                    original = pipeline.generator.generate
                    def counted(*args, **kwargs):
                        invoked.append(True)
                        return original(*args, **kwargs)
                    pipeline.generator.generate = counted
                    try:
                        result = pipeline.answer(case['query'], k=3)
                    finally:
                        pipeline.generator.generate = original
                    if result['context'] != case['context']:
                        raise ValueError('actual supplied context differs from frozen label')
                    name = f"{case['id']}--gate-{mode}.json"
                    write(out / name, result)
                    entry = {'case_id': case['id'], 'condition': mode, 'file': name, 'sha256': sha(out / name),
                             'status': result['status'], 'reason': result['reason'],
                             'generator_invoked': bool(invoked), 'gate_invoked': 'evidence_gate' in result,
                             'gate_status': result.get('evidence_gate', {}).get('status'),
                             'answer': result['answer'], 'seconds': time.monotonic() - before}
                    manifest['attempts'].append(entry)
                    write(out / 'manifest.json', manifest)
                    print(json.dumps(entry, ensure_ascii=False), flush=True)
            gate = LocalSufficiencyGate(endpoint, timeout=120)
            for diagnostic in fixture['diagnostics']:
                before = time.monotonic()
                result = gate.assess(diagnostic['query'], diagnostic['context'])
                name = diagnostic['id'] + '.json'
                write(out / name, result)
                entry = {'case_id': diagnostic['id'], 'condition': 'diagnostic', 'file': name,
                         'sha256': sha(out / name), 'status': result['status'],
                         'gate_invoked': True, 'generator_invoked': False,
                         'seconds': time.monotonic() - before}
                manifest['attempts'].append(entry)
                write(out / 'manifest.json', manifest)
                print(json.dumps(entry, ensure_ascii=False), flush=True)
            status = Path(f'/proc/{process.pid}/status').read_text()
            manifest['memory'] = [x for x in status.splitlines() if x.startswith(('VmRSS:', 'VmHWM:'))]
    except Exception as exc:
        manifest['error'] = type(exc).__name__ + ': ' + str(exc)
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
    print(json.dumps({'server_stopped': manifest['server_stopped'], 'error': manifest.get('error')}), flush=True)
    return int(bool(manifest.get('error')))


if __name__ == '__main__':
    raise SystemExit(main())
