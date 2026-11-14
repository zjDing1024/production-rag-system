"""Offline checks only: no model download, server, inference, or semantic oracle."""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / 'experiments/bilingual-generation-v1'


def module():
    spec = importlib.util.spec_from_file_location('bilingual_audit', EXPERIMENT / 'audit_record.py')
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


class BilingualGenerationRecordTests(unittest.TestCase):
    def test_frozen_pairs_and_source_spans(self):
        fixture = json.loads((EXPERIMENT / 'cases.json').read_text())
        pairs = {}
        for case in fixture['cases']:
            pairs.setdefault(case['pair_id'], set()).add(case['language'])
            for context in case['context']:
                lines = (ROOT / context['path']).read_text().splitlines(keepends=True)
                self.assertEqual(context['text'], ''.join(lines[context['line_start'] - 1:context['line_end']]))
        self.assertEqual(len(pairs), 6)
        self.assertTrue(all(languages == {'en', 'zh'} for languages in pairs.values()))

    def test_audit_reproduces_saved_summary(self):
        self.assertEqual(module().audit(), json.loads((EXPERIMENT / 'summary.json').read_text()))

    def test_schema_shape_does_not_ensure_abstention_contract(self):
        result = module().inspect_form('{"answer":"None","citations":["S1"],"abstain":true}',
                                       'structured_json_schema', ['S1'])
        self.assertTrue(result['json_shape_valid'])
        self.assertFalse(result['contract_valid'])
        self.assertTrue(result['abstain_signal'])

    def test_unknown_citation_and_incomplete_generation_are_rejected(self):
        inspect = module().inspect_form
        content = '{"answer":"output","citations":["S1"],"abstain":false}'
        self.assertTrue(inspect(content, 'structured_json_schema', ['S1'])['contract_valid'])
        self.assertFalse(inspect(content, 'structured_json_schema', ['other'])['contract_valid'])
        self.assertFalse(inspect(content, 'structured_json_schema', ['S1'], 'length')['contract_valid'])

    def test_no_normalization_and_duplicate_keys(self):
        inspect = module().inspect_form
        self.assertFalse(inspect('INSUFFICIENT_EVIDENCE.', 'baseline_text', ['S1'])['contract_valid'])
        self.assertFalse(inspect('S1: output', 'baseline_text', ['S1'])['contract_valid'])
        with self.assertRaises(ValueError):
            module().strict_json('{"answer":"one","answer":"two"}')

    def test_gate_is_not_counted_as_model_abstention(self):
        pipeline = module().audit()['aggregate']['retrieval_pipeline']
        self.assertEqual(pipeline['model_invocations'], 8)
        self.assertEqual(pipeline['gate_abstentions_on_negatives'], 4)
        self.assertEqual(pipeline['valid_model_abstentions_on_negatives'], 0)

    def test_truncated_unsupported_claim_not_hidden_by_primary_format_verdict(self):
        result = next(r for r in module().audit()['rows']
                      if r['mode'] == 'retrieval_pipeline' and r['case_id'] == 'r01-en')
        self.assertEqual(result['manual_verdict'], 'incomplete_output')
        self.assertTrue(result['unsupported_claim_in_raw'])
        self.assertFalse(result['runtime_failure'])
        self.assertFalse(result['contract_valid'])

    def test_tampering_detected_without_model(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / 'fixture'
            shutil.copytree(EXPERIMENT, target, ignore=shutil.ignore_patterns('__pycache__'))
            (target / 'recorded/a01-en--baseline_text.response.raw.json').write_text('{}')
            with self.assertRaisesRegex(ValueError, 'recorded file changed'):
                module().audit(target)

    def test_cli_is_offline_and_serializable(self):
        result = subprocess.run([sys.executable, str(EXPERIMENT / 'audit_record.py')],
                                check=True, capture_output=True, text=True, timeout=10)
        self.assertEqual(json.loads(result.stdout)['record_integrity'], 'verified')


if __name__ == '__main__':
    unittest.main()
