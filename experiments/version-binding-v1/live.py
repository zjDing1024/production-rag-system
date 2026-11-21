"""Explicit six-call CPU comparison; run only after verifying public asset pins."""
import argparse
import hashlib
import http.client
import importlib.util
import json
from pathlib import Path
import socket
import subprocess
import tempfile
import time

from replay import HERE, INPUT, REPO, build_index, slice_case
from rag_foundation.scope_gate import Scope
from rag_foundation.scoped_pipeline import ScopedGenerationPipeline
from rag_foundation.version_bound import answer_with_version_binding

SETUP = REPO / 'experiments' / 'local-generation-smoke' / 'sources.json'


def load_adapter():
    path = REPO / 'experiments' / 'typed-scope-v1' / 'adapter.py'
    spec = importlib.util.spec_from_file_location('version_binding_fixed_adapter', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.BranchedGenerator, module.expected_request


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def ready(process, port):
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError('pinned server exited during startup')
        conn = http.client.HTTPConnection('127.0.0.1', port, timeout=1)
        try:
            conn.request('GET', '/health')
            response = conn.getresponse()
            if response.status == 200 and json.loads(response.read(1024)).get('status') == 'ok':
                return
        except (OSError, ValueError, http.client.HTTPException):
            pass
        finally:
            conn.close()
        time.sleep(.2)
    raise TimeoutError('local server did not become healthy')


def execute(port):
    cases = {c['id']: c for c in json.loads(INPUT.read_text(encoding='utf-8'))['cases']}
    old, new = (cases[f'express-{label}-supported-en'] for label in ('old', 'new'))
    chunks, entries = slice_case(old)
    generator, expected_request = load_adapter()
    client = generator(f'http://127.0.0.1:{port}')
    result = []
    for i, question in enumerate((old, new)):
        query = question['request']['query']
        for j, provider in enumerate((old, new)):
            scope = Scope.from_dict(provider['request']['scope'])
            pipeline = ScopedGenerationPipeline(build_index(chunks, entries), client)
            row = {'question': query, 'question_release': question['request']['scope']['version'],
                   'scope_release': scope.version, 'arms': {}}
            # Alternate within the four frozen pairs. No retries or query changes.
            arms = ('unbound', 'bound') if (i * 2 + j) % 2 == 0 else ('bound', 'unbound')
            for arm in arms:
                client.last_payload = None
                if arm == 'unbound':
                    outcome = pipeline.answer(query, scope, k=1, scope_gate=True)
                    inner = outcome
                else:
                    outcome = answer_with_version_binding(pipeline, query, scope, k=1)
                    inner = outcome['pipeline']
                expected = expected_request(query, inner['context']) if outcome['generator_called'] else None
                if client.last_payload != expected:
                    raise RuntimeError('wire request differed from fixed adapter')
                row['arms'][arm] = {'request': client.last_payload, 'outcome': outcome}
            result.append(row)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--assets', required=True, type=Path)
    args = parser.parse_args()
    with socket.socket() as reservation:
        reservation.bind(('127.0.0.1', 0))
        port = reservation.getsockname()[1]
    sources = json.loads(SETUP.read_text(encoding='utf-8'))
    model, runtime = sources['model'], sources['runtime']
    model_path, binary = args.assets / model['filename'], args.assets / runtime['server_path']
    model_sha, server_sha = sha(model_path), sha(binary)
    if (model_sha, server_sha) != (model['expected_sha256'], runtime['server_sha256']):
        raise ValueError('asset checksum mismatch')
    flags = ['--alias', 'local-model', '--host', '127.0.0.1', '--ctx-size', '4096',
             '--threads', '4', '--threads-batch', '4', '--parallel', '1', '--gpu-layers', '0',
             '--no-agent', '--no-webui', '--no-ui-mcp-proxy', '--reasoning', 'off',
             '--chat-template-kwargs', '{"enable_thinking":false}']
    lock = {
        'cases_sha256': sha(INPUT),
        'replay_sha256': sha(HERE / 'replay.py'),
        'binding_sha256': sha(REPO / 'src/rag_foundation/version_bound.py'),
        'model_sha256': model_sha, 'server_sha256': server_sha, 'server_flags': flags,
    }
    declared = json.loads((HERE / 'live.lock.json').read_text(encoding='utf-8'))
    common = {name: sha(REPO / name) for name in declared['sha256']}
    if common != declared['sha256']:
        raise ValueError('frozen live input changed')
    lock['frozen_input_sha256'] = common
    with tempfile.TemporaryDirectory(dir='/tmp', prefix='version-binding-live.') as d:
        with (Path(d) / 'server.log').open('w', encoding='utf-8') as log:
            # Do not pass user/runner credentials, cache locations or behavior flags.
            env = {'HOME': d, 'XDG_CACHE_HOME': d, 'HF_HUB_OFFLINE': '1', 'LANG': 'C.UTF-8'}
            process = subprocess.Popen(
                [str(binary.resolve()), '--model', str(model_path.resolve()), '--port', str(port), *flags],
                cwd=d, env=env, stdout=log, stderr=log)
            try:
                ready(process, port)
                rows = execute(port)
            finally:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)
    print(json.dumps({'method': 'live-pinned-local-cpu', **lock, 'server_returncode': process.returncode,
                      'rows': rows}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
