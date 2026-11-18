import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock
from rag_foundation.scope_gate import Scope, EvidenceRecord, select_scope, plan, answer, parse_input


class ScopeGateTests(unittest.TestCase):
    def setUp(self):
        self.doc = Scope('documentation', 'Flask', 'KEY', '1.2.3')
        self.run = Scope('runtime', 'Cedar', 'key', observed_at='2031-06-01T09:00:00Z')
        self.a = EvidenceRecord('z9', self.doc, 'value: None', 'https://example.org/source')
        self.b = EvidenceRecord('a2', Scope('documentation', 'Flask', 'KEY', '1.2.4'), 'value: 10', 'https://example.org/other')

    def test_exact_version_selection(self):
        decision, records = select_scope(self.doc, [self.b, self.a])
        self.assertEqual(decision['matched_ids'], ['z9'])
        self.assertIs(records[0], self.a)
        self.assertEqual(decision['rejected'][0]['reason_codes'], ['version_mismatch'])

    def test_entity_and_time_are_both_required(self):
        for scope, reason in [(Scope('runtime', 'Birch', 'key', observed_at=self.run.observed_at), 'subject_mismatch'),
                              (Scope('runtime', 'Cedar', 'key', observed_at='2031-06-01T08:00:00Z'), 'observed_at_mismatch')]:
            r = EvidenceRecord('x', scope, 'value: 17', 'synthetic://fixture')
            result, matches = select_scope(self.run, [r])
            self.assertEqual(result['status'], 'no_match')
            self.assertEqual(result['rejected'][0]['reason_codes'], [reason])
            self.assertEqual(matches, [])

    def test_order_is_preserved_and_ids_are_opaque(self):
        x = EvidenceRecord('Q-other', self.doc, 'another matching passage', 'https://example.org')
        self.assertEqual(select_scope(self.doc, [x, self.a])[0]['matched_ids'], ['Q-other', 'z9'])
        self.assertEqual(select_scope(self.doc, [self.a, x])[0]['matched_ids'], ['z9', 'Q-other'])

    def test_no_match_is_no_run_not_model_refusal(self):
        generator = Mock()
        result = answer('q', self.doc, [self.b], generator, True)
        self.assertEqual(result['status'], 'not_run')
        self.assertEqual(result['reason'], 'no_matching_scope')
        self.assertFalse(result['generator_called'])
        self.assertIsNone(result['generation'])
        generator.generate.assert_not_called()

    def test_default_off_supplies_all_records(self):
        result = plan('q', self.doc, [self.b, self.a])
        self.assertFalse(result['gate_enabled'])
        self.assertIsNone(result['gate'])
        self.assertEqual([c['chunk_id'] for c in result['context']], ['a2', 'z9'])
        self.assertFalse(result['generator_called'])

    def test_none_text_is_evidence_not_absence(self):
        result = plan('q', self.doc, [self.a], True)
        self.assertEqual(result['status'], 'planned')
        self.assertEqual(result['context'][0]['text'], 'value: None')

    def test_generator_status_is_not_reclassified(self):
        for status in ('answered', 'evidence_abstained', 'invalid_response', 'transport_error'):
            generator = Mock()
            generator.generate.return_value = {'status': status, 'reason': 'test'}
            result = answer('q', self.doc, [self.a], generator, True)
            self.assertEqual(result['status'], status)
            self.assertTrue(result['generator_called'])
            self.assertEqual(result['semantic_support'], 'unverified')
            generator.generate.assert_called_once_with('q', [self.a.context()])

    def test_gate_cannot_verify_query_or_text_truth(self):
        forged = EvidenceRecord('forged', self.doc, 'Contradictory or false value: 999', 'synthetic://untrusted-example')
        result = plan('Actually asking a completely different question', self.doc, [forged], True)
        self.assertEqual(result['gate']['matched_ids'], ['forged'])
        self.assertEqual(result['semantic_support'], 'unverified')
        self.assertEqual(result['gate']['trust_boundary'], 'caller_supplied_metadata')

    def test_unknown_scope_or_answer_fields_rejected(self):
        value = {'kind': 'documentation', 'subject': 'Flask', 'key': 'KEY', 'version': '1.2.3', 'observed_at': None}
        for extra in ('expected_answer', 'gold_id', 'query'):
            with self.assertRaises(ValueError):
                Scope.from_dict(dict(value, **{extra: 'leak'}))
        with self.assertRaises(ValueError):
            EvidenceRecord.from_dict({'record_id': 'a', 'scope': value, 'text': 'x', 'citation': 'https://x', 'gold': True})

    def test_timestamp_type_calendar_and_field_conflicts(self):
        for timestamp in ('2031-02-30T09:00:00Z', '2031-06-01', '2031-06-01T09:00:00+00:00', None, True):
            with self.assertRaises(ValueError):
                Scope('runtime', 'Cedar', 'key', observed_at=timestamp)
        with self.assertRaises(ValueError):
            Scope('documentation', 'Flask', 'key', '3.1.2', '2031-06-01T09:00:00Z')
        with self.assertRaises(ValueError):
            Scope('runtime', 'Cedar', 'key', '3.1.2', '2031-06-01T09:00:00Z')

    def test_case_and_version_labels_are_exact_not_fuzzy(self):
        for scope in (Scope('documentation', 'flask', 'KEY', '1.2.3'),
                      Scope('documentation', 'Flask', 'KEY', 'v1.2.3')):
            self.assertEqual(select_scope(scope, [self.a])[0]['status'], 'no_match')

    def test_duplicate_ids_and_size_bounds(self):
        for records in ([self.a, self.a], [self.a] * 13, [None]):
            with self.assertRaises(ValueError):
                select_scope(self.doc, records)
        huge = [EvidenceRecord(str(i), self.doc, 'x' * 4000, 'https://x') for i in range(4)]
        with self.assertRaises(ValueError):
            select_scope(self.doc, huge)
        for rid in (True, '', 'space id', '../a'):
            with self.assertRaises(ValueError):
                EvidenceRecord(rid, self.doc, 'x', 'https://x')

    def test_empty_records_and_invalid_gate_flag(self):
        self.assertEqual(plan('q', self.doc, [], True)['reason'], 'no_matching_scope')
        self.assertEqual(plan('q', self.doc, [])['reason'], 'no_supplied_records')
        with self.assertRaises(ValueError):
            plan('q', self.doc, [self.a], 1)

    def test_strict_input_parser(self):
        with self.assertRaises(ValueError):
            parse_input({'query': 'q', 'scope': {}, 'records': [], 'expected': 'x'})
        with self.assertRaises(ValueError):
            parse_input({'query': 'q', 'scope': {}, 'records': 'wrong'})

    def test_cli_offline_plan(self):
        import dataclasses
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'request.json'
            path.write_text(json.dumps({'query': 'q', 'scope': dataclasses.asdict(self.doc),
                                       'records': [dataclasses.asdict(self.a)]}))
            result = subprocess.run([sys.executable, '-m', 'rag_foundation.scope_gate', str(path), '--gate'],
                                    capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        value = json.loads(result.stdout)
        self.assertEqual(value['status'], 'planned')
        self.assertFalse(value['generator_called'])
        self.assertEqual(value['gate']['matched_ids'], ['z9'])


if __name__ == '__main__':
    unittest.main()
