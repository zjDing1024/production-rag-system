import copy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_fixture import build, render
from protocol import (ExperimentGenerator, answer_request, branch_schema, shape_accepts,
                      validate_answer, make_selector_payload, strict_json)
from preflight_contracts import preflight
from run_experiment import telemetry


class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.context = [{'chunk_id': '1', 'text': 'invented evidence', 'citation': 'synthetic://fixture'}]

    def test_fixture_build_reproduces(self):
        expected = json.loads((Path(__file__).parent / 'cases.json').read_text())
        self.assertEqual(build(), expected)

    def test_same_question_matched_count_order_shape_and_length(self):
        cases = build()['cases']
        for pair_id in {c['pair_id'] for c in cases}:
            a, b = [c for c in cases if c['pair_id'] == pair_id]
            self.assertEqual(a['query'], b['query'])
            self.assertNotEqual(a['offered_sufficient'], b['offered_sufficient'])
            self.assertEqual([s['span_id'] for s in a['spans']], [1, 2])
            self.assertEqual([len(s['text']) for s in a['spans']], [227, 235])
            self.assertEqual([len(s['text']) for s in b['spans']], [227, 235])
            changed = [i for i in range(2) if a['spans'][i]['text'] != b['spans'][i]['text']]
            self.assertEqual(changed, [0] if a['scope'] == 'documentation' else [1])
            i = changed[0]
            self.assertEqual(list(a['spans'][i]['fields']), list(b['spans'][i]['fields']))
            for c in (a, b):
                for span in c['spans']:
                    self.assertEqual(render(span['fields']), span['text'])

    def test_prompt_excludes_source_metadata_and_gold(self):
        case = build()['cases'][0]
        payload = make_selector_payload(case['query'], case['spans'], 'numbered_span')
        value = json.loads(payload['messages'][1]['content'])
        self.assertEqual(set(value), {'question', 'offered_spans'})
        for span in value['offered_spans']:
            self.assertEqual(set(span), {'span_id', 'text'})

    def test_only_generation_schema_differs(self):
        a, b = [answer_request('q', self.context, arm) for arm in ('legacy', 'branched')]
        self.assertNotEqual(a['response_format']['json_schema']['schema'], b['response_format']['json_schema']['schema'])
        for payload in (a, b):
            del payload['response_format']['json_schema']['schema']
        self.assertEqual(a, b)

    def test_whole_branch_no_mixed_root_properties(self):
        schema = branch_schema(['1'])
        self.assertEqual(set(schema), {'anyOf'})
        self.assertEqual(len(schema['anyOf']), 2)
        self.assertEqual(schema['anyOf'][0]['properties']['abstain'], {'const': False})
        self.assertEqual(schema['anyOf'][1]['properties']['answer'], {'const': ''})

    def test_valid_answer_and_refusal(self):
        for value in ({'answer': '7', 'citations': ['1'], 'abstain': False},
                      {'answer': '', 'citations': [], 'abstain': True}):
            self.assertTrue(shape_accepts(value, ['1'], 'branched'))
            self.assertEqual(validate_answer(value, ['1']), value)

    def test_schema_targeted_rejections(self):
        for value in ({'answer': '7', 'citations': [], 'abstain': False},
                      {'answer': 'unknown', 'citations': [], 'abstain': True}):
            self.assertTrue(shape_accepts(value, ['1'], 'legacy'))
            self.assertFalse(shape_accepts(value, ['1'], 'branched'))

    def test_python_only_whitespace_and_duplicate_checks(self):
        for value in ({'answer': ' ', 'citations': ['1'], 'abstain': False},
                      {'answer': 'a', 'citations': ['1', '1'], 'abstain': False}):
            self.assertTrue(shape_accepts(value, ['1'], 'branched'))
            with self.assertRaises(ValueError):
                validate_answer(value, ['1'])

    def test_unknown_bool_and_empty_id_rejected(self):
        for ids in ([], [''], [True], ['1', '1'], [None], [{}]):
            with self.assertRaises(ValueError):
                branch_schema(ids)
        self.assertFalse(shape_accepts({'answer': 'a', 'citations': ['9'], 'abstain': False}, ['1'], 'branched'))

    def test_actual_wrapper_payload_and_validation(self):
        for arm in ('legacy', 'branched'):
            connection, response = Mock(), Mock()
            connection.getresponse.return_value = response
            response.status = 200
            response.read.return_value = json.dumps({'choices': [{'finish_reason': 'stop',
                'message': {'content': '{"answer":"7","citations":["1"],"abstain":false}'}}]}).encode()
            generator = ExperimentGenerator()
            with patch('protocol.http.client.HTTPConnection', return_value=connection):
                result = generator.generate_arm('q', self.context, arm)
            self.assertEqual(result['status'], 'answered')
            self.assertEqual(generator.last_payload, answer_request('q', self.context, arm))
            connection.close.assert_called_once()

    def test_transports_and_invalid_contract_not_refusal(self):
        connection = Mock()
        connection.request.side_effect = OSError('unavailable')
        with patch('protocol.http.client.HTTPConnection', return_value=connection):
            result = ExperimentGenerator().generate_arm('q', self.context, 'branched')
        self.assertEqual(result['status'], 'transport_error')
        with self.assertRaises(ValueError):
            strict_json('{"x":1,"x":2}')

    def test_archived_preflight_is_not_native_claim(self):
        result = preflight()
        self.assertEqual(len(result['historical_regressions']), 11)
        self.assertEqual(sum(r['legacy_schema_shape'] for r in result['historical_regressions']), 11)
        self.assertEqual(sum(r['branched_schema_shape'] for r in result['historical_regressions']), 1)
        self.assertEqual(result, json.loads((Path(__file__).parent / 'preflight.json').read_text()))

    def test_evidence_blind_baseline_cannot_solve_pairs(self):
        cases = build()['cases']
        for policy in (lambda c: True, lambda c: False, lambda c: c['scope'] == 'documentation'):
            self.assertEqual(sum(policy(c) == c['offered_sufficient'] for c in cases), 8)
            self.assertEqual(sum(all(policy(c) == c['offered_sufficient'] for c in cases if c['pair_id'] == p)
                                 for p in {c['pair_id'] for c in cases}), 0)

    def test_telemetry_best_effort(self):
        with patch.object(Path, 'read_text', side_effect=OSError('unavailable')):
            self.assertEqual(telemetry(1)['status'], 'unavailable')


if __name__ == '__main__':
    unittest.main()
