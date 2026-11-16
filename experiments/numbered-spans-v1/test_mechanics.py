import copy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mechanics import SpanSelector, make_payload, validate_selection, validate_spans
from run_experiment import memory_telemetry


class MechanicsTests(unittest.TestCase):
    def setUp(self):
        self.spans = [{'span_id': 1, 'text': 'Default: ``31``\n  days.',
                       'source_url': 'https://example.org/source', 'secret_gold': 'not a prompt'}]

    def test_same_offered_text_and_enum_no_metadata(self):
        a = make_payload('Which default?', self.spans, 'exact_quote')
        b = make_payload('Which default?', self.spans, 'numbered_span')
        self.assertEqual(a['messages'][1], b['messages'][1])
        self.assertEqual(json.loads(a['messages'][1]['content']), {
            'question': 'Which default?', 'offered_spans': [{'span_id': 1, 'text': self.spans[0]['text']}]})
        for payload in (a, b):
            props = payload['response_format']['json_schema']['schema']['properties']
            self.assertEqual(props['selections']['items']['properties']['span_id']['enum'], [1])
            self.assertEqual(props['selections']['maxItems'], 1)
            self.assertEqual(payload['max_tokens'], 512)

    def test_whole_quote_and_id_resolve_identical_original(self):
        a = validate_selection({'sufficient': True, 'selections': [
            {'span_id': 1, 'quote': self.spans[0]['text']}]}, self.spans, 'exact_quote')
        b = validate_selection({'sufficient': True, 'selections': [{'span_id': 1}]},
                               self.spans, 'numbered_span')
        self.assertEqual(a, b)
        self.assertIs(a[0], self.spans[0])

    def test_both_arms_allow_empty_insufficient(self):
        for arm in ('exact_quote', 'numbered_span'):
            self.assertEqual(validate_selection({'sufficient': False, 'selections': []}, self.spans, arm), [])

    def test_substring_or_normalization_is_not_exact(self):
        for quote in ('31', self.spans[0]['text'].replace('\n  ', ' '), self.spans[0]['text'] + '\n'):
            with self.assertRaises(ValueError):
                validate_selection({'sufficient': True, 'selections': [{'span_id': 1, 'quote': quote}]},
                                   self.spans, 'exact_quote')

    def test_invalid_selection_fields_types_and_cardinality(self):
        invalid = [
            {'sufficient': True, 'selections': []},
            {'sufficient': False, 'selections': [{'span_id': 1}]},
            {'sufficient': 1, 'selections': [{'span_id': 1}]},
            {'sufficient': True, 'selections': [{'span_id': True}]},
            {'sufficient': True, 'selections': [{'span_id': 2}]},
            {'sufficient': True, 'selections': [{'span_id': 1}, {'span_id': 1}]},
            {'sufficient': True, 'selections': [{'span_id': 1, 'quote': 'extra'}]},
            {'sufficient': False, 'selections': [], 'extra': 1},
        ]
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_selection(value, self.spans, 'numbered_span')

    def test_span_bounds_and_non_dict(self):
        invalid = [[], [None], ['text'], [{'span_id': True, 'text': 'a'}],
                   [{'span_id': 2, 'text': 'a'}], [{'span_id': 1, 'text': ''}],
                   [{'span_id': 1, 'text': 'a' * 601}],
                   [{'span_id': i, 'text': 'a' * 600} for i in range(1, 10)],
                   [{'span_id': i, 'text': 'a'} for i in range(1, 14)]]
        for spans in invalid:
            with self.subTest(spans=spans), self.assertRaises(ValueError):
                validate_spans(spans)

    def test_external_endpoint_is_rejected(self):
        for endpoint in ('https://127.0.0.1:8080', 'http://example.org', 'http://127.0.0.1:80/path'):
            with self.assertRaises(ValueError):
                SpanSelector(endpoint)

    def response(self, content, finish='stop', status=200):
        response = Mock()
        response.status = status
        response.read.return_value = json.dumps({'choices': [{'finish_reason': finish,
            'message': {'content': content}}]}).encode()
        connection = Mock()
        connection.getresponse.return_value = response
        return connection

    def test_selector_success_uses_original_text(self):
        conn = self.response('{"sufficient":true,"selections":[{"span_id":1}]}')
        with patch('mechanics.http.client.HTTPConnection', return_value=conn):
            value = SpanSelector().select('Which default?', self.spans, 'numbered_span')
        self.assertEqual(value['status'], 'selected')
        self.assertEqual(value['selected_context'][0]['text'], self.spans[0]['text'])
        self.assertEqual(value['semantic_support'], 'unverified')
        conn.close.assert_called_once()

    def test_invalid_duplicate_and_incomplete_are_not_refusals(self):
        for content, finish in [('{"sufficient":false,"sufficient":false,"selections":[]}', 'stop'),
                                ('{"sufficient":false,"selections":[]}', 'length')]:
            with patch('mechanics.http.client.HTTPConnection', return_value=self.response(content, finish)):
                value = SpanSelector().select('q', self.spans, 'numbered_span')
            self.assertEqual(value['status'], 'invalid_response')

    def test_http_and_transport_errors_are_not_refusals(self):
        with patch('mechanics.http.client.HTTPConnection', return_value=self.response('x', status=500)):
            self.assertEqual(SpanSelector().select('q', self.spans, 'numbered_span')['status'], 'transport_error')
        conn = Mock()
        conn.request.side_effect = OSError('unavailable')
        with patch('mechanics.http.client.HTTPConnection', return_value=conn):
            self.assertEqual(SpanSelector().select('q', self.spans, 'numbered_span')['status'], 'transport_error')

    def test_memory_telemetry_failure_is_nonfatal(self):
        with patch.object(Path, 'read_text', side_effect=OSError('unavailable')):
            self.assertEqual(memory_telemetry(1)['status'], 'unavailable')


if __name__ == '__main__':
    unittest.main()
