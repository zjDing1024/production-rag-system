"""Protocol and gate integration tests; fake decisions are not semantic evidence."""
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
import threading
import unittest
from unittest.mock import patch

from rag_foundation.generation import GenerationPipeline
from rag_foundation.sufficiency import LocalSufficiencyGate, validate_decision

ROOT = Path(__file__).resolve().parents[1]
CONTEXT = [{'chunk_id': 'c1', 'text': 'The documented limit is 100 bytes.', 'citation': 'source:1'}]


class SufficiencyTests(unittest.TestCase):
    def test_quote_contract(self):
        valid = {'sufficient': True, 'evidence': [{'chunk_id': 'c1', 'quote': 'limit is 100 bytes'}]}
        self.assertEqual(validate_decision(valid, CONTEXT), valid)
        for bad in [dict(valid, sufficient=1), dict(valid, evidence=[]), dict(valid, extra=1),
                    {'sufficient': False, 'evidence': valid['evidence']},
                    {'sufficient': True, 'evidence': valid['evidence']*2},
                    {'sufficient': True, 'evidence': [{'chunk_id': 'bad', 'quote': 'limit is 100 bytes'}]},
                    {'sufficient': True, 'evidence': [{'chunk_id': 'c1', 'quote': 'limit is 500 bytes'}]},
                    {'sufficient': True, 'evidence': [{'chunk_id': 'c1', 'quote': 'is'}]},
                    {'sufficient': True, 'evidence': [{'chunk_id': 'c1', 'quote': '\ud800'}]}]:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                validate_decision(bad, CONTEXT)

    def request(self, body, status=200):
        seen = []
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                seen.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
                self.send_response(status)
                self.end_headers()
                self.wfile.write(body)
            def log_message(self, *args):
                pass
        server = HTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.handle_request)
        thread.start()
        result = LocalSufficiencyGate(f'http://127.0.0.1:{server.server_port}').assess('limit?', CONTEXT)
        thread.join(5)
        server.server_close()
        self.assertFalse(thread.is_alive())
        return result, seen

    def envelope(self, value, finish='stop'):
        return json.dumps({'choices': [{'finish_reason': finish, 'message': {'content': json.dumps(value)}}]}).encode()

    def test_sufficient_socket(self):
        result, seen = self.request(self.envelope({'sufficient': True, 'evidence': [
            {'chunk_id': 'c1', 'quote': 'limit is 100 bytes'}]}))
        self.assertEqual(result['status'], 'sufficient')
        self.assertEqual(seen[0]['temperature'], 0)
        self.assertEqual(seen[0]['seed'], 42)
        self.assertEqual(seen[0]['max_tokens'], 512)
        self.assertEqual(json.loads(seen[0]['messages'][1]['content'])['source_excerpts'][0]['text'], CONTEXT[0]['text'])

    def test_insufficient_socket(self):
        self.assertEqual(self.request(self.envelope({'sufficient': False, 'evidence': []}))[0]['status'], 'insufficient')

    def test_invalid_is_not_rejection(self):
        for body in [b'{}', b'bad', b'x'*262145, b'{"choices":[],"choices":[]}',
                     self.envelope({'sufficient': True, 'evidence': []}),
                     self.envelope({'sufficient': False, 'evidence': []}, 'length')]:
            self.assertEqual(self.request(body)[0]['status'], 'invalid_response')

    def test_transport_is_not_rejection(self):
        self.assertEqual(self.request(b'\xff', 503)[0]['status'], 'transport_error')
        with patch('http.client.HTTPConnection.request', side_effect=TimeoutError):
            self.assertEqual(LocalSufficiencyGate().assess('q', CONTEXT)['status'], 'transport_error')

    def test_evidence_replacement_invalidates_exact_quote(self):
        value = {'sufficient': True, 'evidence': [{'chunk_id': 'c1', 'quote': 'limit is 100 bytes'}]}
        validate_decision(value, CONTEXT)
        with self.assertRaises(ValueError):
            validate_decision(value, [{'chunk_id': 'c1', 'text': 'The value is not given.'}])

    def test_default_off_preserves_route(self):
        pipe = GenerationPipeline(ROOT)
        self.assertIsNone(pipe.sufficiency_gate)
        with patch.object(pipe.generator, 'generate', return_value={'status': 'transport_error'}) as generator:
            result = pipe.answer('logging')
        self.assertNotIn('evidence_gate', result)
        self.assertEqual(result['status'], 'transport_error')
        self.assertEqual(generator.call_count, 1)

    def test_gate_fail_closed_preserves_error_category(self):
        pipe = GenerationPipeline(ROOT, evidence_gate=True)
        for status in ('insufficient', 'invalid_response', 'transport_error'):
            with patch.object(pipe.sufficiency_gate, 'assess', return_value={'status': status, 'reason': 'fixture'}):
                with patch.object(pipe.generator, 'generate', side_effect=AssertionError('must not generate')):
                    result = pipe.answer('logging')
            self.assertEqual(result['status'], 'evidence_abstained' if status == 'insufficient' else status)
            self.assertIsNone(result['answer'])
            self.assertEqual(result['citation_ids'], [])

    def test_pass_preserves_context_and_generator_errors(self):
        pipe = GenerationPipeline(ROOT, evidence_gate=True)
        with patch.object(pipe.sufficiency_gate, 'assess', return_value={'status': 'sufficient'}) as gate:
            with patch.object(pipe.generator, 'generate', return_value={'status': 'invalid_response'}) as generate:
                result = pipe.answer('logging')
        self.assertEqual(gate.call_args, generate.call_args)
        self.assertEqual(result['status'], 'invalid_response')

    def test_flag_must_be_bool(self):
        with self.assertRaises(ValueError):
            GenerationPipeline(ROOT, evidence_gate=1)

    def test_cli_flag(self):
        from rag_foundation.generation import main
        with patch('sys.argv', ['generation', 'logging', '--evidence-gate']):
            with patch('rag_foundation.generation.GenerationPipeline') as cls:
                cls.return_value.answer.return_value = {'status': 'fixture_only'}
                with patch('builtins.print'):
                    main()
                self.assertTrue(cls.call_args.kwargs['evidence_gate'])


if __name__ == '__main__':
    unittest.main()
