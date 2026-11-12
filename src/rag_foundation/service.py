"""Local-only bounded HTTP retrieval, with transparent query expansion and gating.

No LLM, no answerability classifier, no externally supplied paths or URLs.
"""
import argparse
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
import re

from .corpus import build_chunks, canonical_json, digest, load_corpus
from .retrieval import BM25, tokenize

POLICY = 'lexical-coverage-v1'
# Authored glossary, not a multilingual model. Exposed in each response.
GLOSSARY = {
    '测试客户端': 'test client', '真实服务器': 'live server',
    '服务器': 'server', '测试': 'testing', '日志': 'logging',
    '重定向': 'redirect', '路由': 'route', '异常': 'exception',
    '会话': 'session', '密钥': 'secret key', '静态文件': 'static files',
    '反向代理': 'reverse proxy', '生产环境': 'production',
}
STOP = set('a an the i we you do does how what which when where why can is are be to of for in on and or with from instead only should my it while no not as by at will'.split())


def expand(query):
    expanded = query
    aliases = []
    # Longest first prevents replacing substrings before their phrase.
    for phrase in sorted(GLOSSARY, key=lambda x: (-len(x), x)):
        if phrase in expanded:
            aliases.append({'source': phrase, 'replacement': GLOSSARY[phrase]})
            expanded = expanded.replace(phrase, ' ' + GLOSSARY[phrase] + ' ')
    # Remaining Chinese is not translated or silently declared supported.
    return expanded, aliases


class RetrievalService:
    def __init__(self, root: Path):
        self.chunks = build_chunks(load_corpus(root))
        self.index = BM25(self.chunks)
        self.fingerprint = digest(canonical_json([asdict(c) for c in self.chunks]).encode())

    def retrieve(self, payload):
        if not isinstance(payload, dict) or set(payload) - {'query', 'k', 'expand_zh', 'gate'}:
            raise ValueError('expected query and optional k, expand_zh, gate only')
        query = payload.get('query')
        k = payload.get('k', 5)
        expand_zh = payload.get('expand_zh', True)
        gate = payload.get('gate', True)
        if not isinstance(query, str) or not query.strip() or len(query) > 1000:
            raise ValueError('query must contain 1..1000 characters')
        if type(k) is not int or not 1 <= k <= 10:
            raise ValueError('k must be an integer in 1..10')
        if type(expand_zh) is not bool or type(gate) is not bool:
            raise ValueError('expand_zh and gate must be booleans')
        effective, aliases = expand(query) if expand_zh else (query, [])
        # CJK sentences cannot be segmented by the baseline tokenizer. Measure
        # Latin technical terms only, and explicitly disclose unknown language.
        terms = set(re.findall(r'[a-z0-9_]+', effective.casefold())) - STOP - {'flask'}
        known = terms & self.index.postings.keys()
        coverage = len(known) / len(terms) if terms else 0.0
        hits = self.index.search(effective, k)
        passed = bool(terms) and coverage >= 0.6
        status = 'candidates' if hits and (passed or not gate) else 'abstained'
        return {'mode': 'retrieval-only', 'answer': None, 'answerability': 'unverified',
                'status': status, 'query': query, 'effective_query': effective,
                'aliases': aliases, 'untranslated_cjk': bool(re.search(r'[\u3400-\u9fff]', effective)),
                'policy': {'version': POLICY, 'enabled': gate, 'threshold': 0.6,
                           'coverage': coverage, 'missing_terms': sorted(terms - known),
                           'passed': passed, 'meaning': 'corpus-vocabulary coverage, not confidence'},
                'chunks_sha256': self.fingerprint,
                'results': [h.to_dict() for h in hits] if status == 'candidates' else [],
                'candidate_count_before_gate': len(hits)}


def make_server(service, port=8000):
    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(3)

        def log_message(self, *args):
            pass  # Do not log query content.

        def send_json(self, code, value):
            body = canonical_json(value).encode()
            self.send_response(code)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path != '/health':
                return self.send_json(404, {'error': 'not found'})
            self.send_json(200, {'mode': 'retrieval-only', 'chunks': len(service.chunks),
                                 'chunks_sha256': service.fingerprint})

        def do_POST(self):
            if self.path != '/retrieve':
                return self.send_json(404, {'error': 'not found'})
            if self.headers.get_content_type() != 'application/json':
                return self.send_json(415, {'error': 'application/json required'})
            lengths = self.headers.get_all('Content-Length', [])
            if len(lengths) != 1 or self.headers.get('Transfer-Encoding'):
                return self.send_json(400, {'error': 'one Content-Length required; no transfer encoding'})
            try:
                length = int(lengths[0])
                if not 0 < length <= 8192:
                    return self.send_json(413, {'error': 'body must be 1..8192 bytes'})
                body = self.rfile.read(length)
                if len(body) != length:
                    raise ValueError('incomplete body')
                payload = json.loads(body)
                result = service.retrieve(payload)
            except (ValueError, UnicodeError, RecursionError, TimeoutError):
                return self.send_json(400, {'error': 'invalid request'})
            self.send_json(200, result)
    # Intentionally loopback and single request at a time. Not a public deployment.
    return HTTPServer(('127.0.0.1', port), Handler)


def main():
    parser = argparse.ArgumentParser(description='Local retrieval demo, not production HTTP hosting')
    parser.add_argument('--root', type=Path, default=Path('.'))
    parser.add_argument('--port', type=int, default=8000)
    args = parser.parse_args()
    with make_server(RetrievalService(args.root), args.port) as server:
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == '__main__':
    main()
