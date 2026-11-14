"""Contract tests use a fake socket server, never pretend to be model quality."""
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
import threading
import unittest
from unittest.mock import patch

from rag_foundation.generation import GenerationPipeline, LocalGenerator, validate_answer, safe_usage, strict_json

ROOT = Path(__file__).resolve().parents[1]


class GenerationTests(unittest.TestCase):
    def test_strict_citation_contract(self):
        good = {'answer': 'A', 'citations': ['c1'], 'abstain': False}
        self.assertEqual(validate_answer(good, ['c1']), good)
        for bad in [dict(good, citations=['wrong']), dict(good, citations=['c1', 'c1']),
                    dict(good, citations=[]), dict(good, answer=' '), dict(good, abstain=1),
                    dict(good, extra=True), dict(good, citations=[1]),
                    dict(good, answer='x'*4001), dict(good, abstain=True), dict(good, answer='\ud800')]:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                validate_answer(bad, ['c1'])
        self.assertEqual(validate_answer({'answer': '', 'citations': [], 'abstain': True}, []),
                         {'answer': '', 'citations': [], 'abstain': True})

    def test_usage_is_sanitized(self):
        self.assertIsNone(safe_usage('\ud800'))
        self.assertEqual(safe_usage({'prompt_tokens': 3, 'total_tokens': True,
                                    'completion_tokens': -1, 'untrusted': '\ud800'}),
                         {'prompt_tokens': 3})
        with self.assertRaises(ValueError):
            strict_json('{"usage":1e999}')

    def test_only_loopback(self):
        for url in ['https://127.0.0.1:80', 'http://localhost:80', 'http://example.org',
                    'http://127.0.0.1/a', 'http://user:pass@127.0.0.1', 'http://127.0.0.1?x=1']:
            with self.subTest(url=url), self.assertRaises(ValueError):
                LocalGenerator(url)

    def run_server(self, body, code=200):
        captured = []
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                captured.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
                self.send_response(code)
                if code == 302:
                    self.send_header('Location', 'http://example.invalid/external')
                self.end_headers()
                self.wfile.write(body)
            def log_message(self, *args):
                pass
        server = HTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.handle_request)
        thread.start()
        result = LocalGenerator(f'http://127.0.0.1:{server.server_port}').generate(
            'Question?', [{'chunk_id': 'c1', 'text': 'Public source'}])
        thread.join(timeout=5)
        server.server_close()
        self.assertFalse(thread.is_alive())
        return result, captured

    def envelope(self, content, finish='stop'):
        return json.dumps({'choices': [{'finish_reason': finish, 'message': {
            'content': json.dumps(content)}}]}).encode()

    def test_answer_socket(self):
        result, requests = self.run_server(self.envelope({'answer': 'A', 'citations': ['c1'], 'abstain': False}))
        self.assertEqual(result['status'], 'answered')
        self.assertTrue(result['raw_response'])
        self.assertEqual(requests[0]['response_format']['type'], 'json_schema')
        self.assertFalse(requests[0]['chat_template_kwargs']['enable_thinking'])

    def test_model_abstention_is_not_error(self):
        result, _ = self.run_server(self.envelope({'answer': '', 'citations': [], 'abstain': True}))
        self.assertEqual(result['status'], 'evidence_abstained')
        self.assertEqual(result['reason'], 'model_abstention')

    def test_invalid_not_counted_as_abstention(self):
        for body in [b'bad json', b'\xff', b'{}', self.envelope({'answer': 'A', 'citations': ['bad'], 'abstain': False}),
                     self.envelope({'answer': '', 'citations': [], 'abstain': True}, 'length')]:
            with self.subTest(body=body):
                self.assertEqual(self.run_server(body)[0]['status'], 'invalid_response')

    def test_http_error_not_evidence_abstention(self):
        result, _ = self.run_server(b'{"error":"busy"}', 503)
        self.assertEqual(result['status'], 'transport_error')
        self.assertEqual(result['reason'], 'http_503')
        binary, _ = self.run_server(b'\xff', 503)
        self.assertEqual(binary['status'], 'transport_error')
        self.assertEqual(binary['reason'], 'http_503')

    def test_duplicate_json_keys_rejected(self):
        inner = '{"answer":"A","answer":"B","citations":["c1"],"abstain":false}'
        outer = json.dumps({'choices': [{'finish_reason': 'stop', 'message': {'content': inner}}]}).encode()
        for body in [outer, b'{"choices":[],"choices":[]}', b'{"choices":NaN}']:
            self.assertEqual(self.run_server(body)[0]['status'], 'invalid_response')

    def test_oversize_response(self):
        self.assertEqual(self.run_server(b'x'*262145)[0]['status'], 'invalid_response')

    def test_redirect_not_followed(self):
        result, captured = self.run_server(b'elsewhere', 302)
        self.assertEqual(result['status'], 'transport_error')
        self.assertEqual(result['reason'], 'http_302')
        self.assertEqual(len(captured), 1)

    def test_timeout_not_abstention(self):
        with patch('http.client.HTTPConnection.getresponse', side_effect=TimeoutError):
            with patch('http.client.HTTPConnection.request'):
                result = LocalGenerator().generate('q', [{'chunk_id': 'c1', 'text': 't'}])
        self.assertEqual(result['status'], 'transport_error')

    def test_pipeline_preserves_errors(self):
        pipe = GenerationPipeline(ROOT)
        for status in ('transport_error', 'invalid_response'):
            with patch.object(pipe.generator, 'generate', return_value={'status': status, 'raw_response': 'error'}):
                result = pipe.answer('logging')
            self.assertEqual(result['status'], status)
            self.assertIsNone(result['answer'])
            self.assertEqual(result['citation_ids'], [])

    def test_connection_failure(self):
        with patch('http.client.HTTPConnection.request', side_effect=ConnectionRefusedError):
            result = LocalGenerator().generate('q', [{'chunk_id': 'c1', 'text': 't'}])
        self.assertEqual(result['status'], 'transport_error')

    def test_empty_retrieval_does_not_call_model(self):
        pipe = GenerationPipeline(ROOT)
        with patch.object(pipe.generator, 'generate', side_effect=AssertionError('unexpected call')):
            result = pipe.answer('zqxv blorptastic neutrinoquux')
        self.assertEqual(result['status'], 'evidence_abstained')
        self.assertEqual(result['reason'], 'no_retrieved_context')
        self.assertIsNone(result['raw_response'])

    def test_pipeline_maps_source_citations(self):
        pipe = GenerationPipeline(ROOT)
        def fake(query, context):
            return {'status': 'answered', 'answer': 'Test fixture only', 'citation_ids': [context[0]['chunk_id']]}
        with patch.object(pipe.generator, 'generate', side_effect=fake):
            result = pipe.answer('test client live server')
        self.assertEqual(len(result['citations']), 1)
        self.assertEqual(result['semantic_support'], 'unverified')
        self.assertEqual(result['citations'][0]['citation'], result['context'][0]['citation'])
        with self.assertRaises(ValueError):
            pipe.answer('logging', k=True)


if __name__ == '__main__':
    unittest.main()
