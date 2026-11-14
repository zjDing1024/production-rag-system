"""Opt-in CPU experiment: one local server, frozen inputs, no request retries.

Fixed-context text/schema comparison is separate from real retrieval->generation.
Network-facing inference stays on loopback within this process's environment.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import http.client
import importlib
import json
import os
from pathlib import Path
import platform
import socket
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def sha(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def write_json(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def request_schema():
    return {'type': 'object', 'additionalProperties': False,
            'properties': {'answer': {'type': 'string'},
                           'citations': {'type': 'array', 'items': {'type': 'string', 'enum': ['S1']},
                                         'maxItems': 3}, 'abstain': {'type': 'boolean'}},
            'required': ['answer', 'citations', 'abstain']}


def make_request(case, mode, fixture):
    context = '\n\n'.join(f"[{item['id']}] {item['text']}" for item in case['context'])
    payload = {'model': 'local-model', 'temperature': fixture['plan']['temperature'],
               'seed': fixture['plan']['seed'], 'max_tokens': fixture['plan']['max_tokens'],
               'stream': False, 'chat_template_kwargs': {'enable_thinking': False},
               'messages': [{'role': 'system', 'content': fixture['prompts'][mode]},
                            {'role': 'user', 'content': f"CONTEXT:\n{context}\n\nQUESTION:\n{case['query']}"}]}
    if mode == 'structured_json_schema':
        payload['response_format'] = {'type': 'json_schema', 'json_schema': {
            'name': 'cited_answer', 'strict': True, 'schema': request_schema()}}
    return payload


def fixed_request(port, payload):
    connection = http.client.HTTPConnection('127.0.0.1', port, timeout=120)
    try:
        connection.request('POST', '/v1/chat/completions', json.dumps(payload, ensure_ascii=False).encode(),
                           {'Content-Type': 'application/json'})
        response = connection.getresponse()
        body = response.read(262145)
        if len(body) > 262144:
            raise ValueError('response exceeds 256 KiB')
        return response.status, body
    finally:
        connection.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=REPO / 'build/bilingual-generation-v1-run-001')
    parser.add_argument('--adapter-source', type=Path, default=REPO / 'src')
    parser.add_argument('--mode', choices=['all', 'fixed', 'pipeline'], default='all')
    args = parser.parse_args()
    out = args.output.resolve()
    if not out.is_relative_to(REPO / 'build'):
        raise ValueError('output must be a new directory under repository build/')
    out.mkdir(parents=True, exist_ok=False)
    fixture = json.loads((HERE / 'cases.json').read_text())
    lock = json.loads((HERE / 'cases.lock.json').read_text())
    if sha(HERE / 'cases.json') != lock['cases_sha256']:
        raise ValueError('frozen cases changed')
    artifacts = REPO / 'experiments/local-generation-smoke'
    sources = json.loads((artifacts / 'sources.json').read_text())
    model = artifacts / sources['model']['filename']
    binary = artifacts / sources['runtime']['server_path']
    if sha(model) != sources['model']['expected_sha256'] or sha(binary) != sources['runtime']['server_sha256']:
        raise ValueError('model or runtime checksum mismatch; run the pinned prepare.py')
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    flags = ['--model', str(model), '--alias', 'local-model', '--host', '127.0.0.1', '--port', str(port),
             '--ctx-size', str(fixture['plan']['context_tokens']), '--threads', '4', '--threads-batch', '4',
             '--parallel', '1', '--gpu-layers', '0', '--no-agent', '--no-webui', '--no-ui-mcp-proxy',
             '--reasoning', 'off', '--chat-template-kwargs', '{"enable_thinking":false}']
    env = {k: v for k, v in os.environ.items()
           if not k.startswith('LLAMA_') and k not in {'HF_TOKEN', 'HUGGING_FACE_HUB_TOKEN'}}
    for key, folder in [('HOME', 'home'), ('XDG_CACHE_HOME', 'cache')]:
        path = out / folder
        path.mkdir()
        env[key] = str(path)
    env['HF_HUB_OFFLINE'] = '1'
    manifest = {'schema_version': 1, 'started_utc': datetime.now(timezone.utc).isoformat(),
                'cases_sha256': lock['cases_sha256'], 'runner_sha256': sha(Path(__file__)),
                'model_sha256': sha(model), 'runtime_sha256': sha(binary),
                'python': platform.python_version(), 'mode': args.mode,
                'server_flags': [model.name if x == str(model) else '<ephemeral>' if x == str(port) else x for x in flags],
                'requests': [], 'scope': fixture['scope']}
    process = None
    started = time.monotonic()
    try:
        with (out / 'server.log').open('w') as log:
            process = subprocess.Popen([str(binary)] + flags, env=env, cwd=REPO, stdout=log, stderr=log)
            while time.monotonic() - started < 60:
                if process.poll() is not None:
                    raise RuntimeError(f'server exited: {process.returncode}')
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
                raise TimeoutError('server startup exceeded 60 seconds')
            manifest['startup_seconds'] = time.monotonic() - started
            if args.mode in ('all', 'fixed'):
                for case in fixture['cases']:
                    for mode in fixture['plan']['fixed_context_modes']:
                        name = f"{case['id']}--{mode}"
                        payload = make_request(case, mode, fixture)
                        write_json(out / f'{name}.request.json', payload)
                        entry = {'case_id': case['id'], 'mode': mode}
                        before = time.monotonic()
                        try:
                            status, body = fixed_request(port, payload)
                            path = out / f'{name}.response.raw.json'
                            path.write_bytes(body)
                            entry.update(http_status=status, raw_file=path.name, raw_sha256=sha(path),
                                         request_file=f'{name}.request.json', runtime_status='completed' if status == 200 else 'http_error')
                            if status == 200:
                                response = json.loads(body)
                                entry.update(content=response['choices'][0]['message']['content'],
                                             finish_reason=response['choices'][0]['finish_reason'], usage=response.get('usage'))
                        except Exception as exc:
                            entry.update(runtime_status='failed', error=type(exc).__name__)
                        entry['seconds'] = time.monotonic() - before
                        manifest['requests'].append(entry)
                        write_json(out / 'manifest.json', manifest)
                        print(json.dumps(entry, ensure_ascii=False), flush=True)
            if args.mode in ('all', 'pipeline'):
                sys.path.insert(0, str(args.adapter_source.resolve()))
                module = importlib.import_module('rag_foundation.generation')
                manifest['adapter_sha256'] = sha(Path(module.__file__))
                pipeline = module.GenerationPipeline(REPO, f'http://127.0.0.1:{port}', timeout=120)
                for case in fixture['cases']:
                    before = time.monotonic()
                    result = pipeline.answer(case['query'], k=3)
                    path = out / f"{case['id']}--pipeline.json"
                    write_json(path, result)
                    entry = {'case_id': case['id'], 'mode': 'retrieval_pipeline',
                             'status': result['status'], 'reason': result['reason'],
                             'result_file': path.name, 'result_sha256': sha(path),
                             'model_invoked': result['raw_response'] is not None,
                             'answer': result['answer'], 'seconds': time.monotonic() - before}
                    manifest['requests'].append(entry)
                    write_json(out / 'manifest.json', manifest)
                    print(json.dumps(entry, ensure_ascii=False), flush=True)
            status = Path(f'/proc/{process.pid}/status').read_text()
            manifest['memory'] = [line for line in status.splitlines() if line.startswith(('VmRSS:', 'VmHWM:'))]
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
        write_json(out / 'manifest.json', manifest)
    print(json.dumps({'server_stopped': manifest['server_stopped'], 'error': manifest.get('error')}), flush=True)
    return int(bool(manifest.get('error')))


if __name__ == '__main__':
    raise SystemExit(main())
