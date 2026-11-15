"""Recorded-evidence checks only. No downloads, server, or model execution."""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent


def audit_module():
    spec = importlib.util.spec_from_file_location('evidence_audit', HERE / 'audit_record.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class EvidenceRecordTests(unittest.TestCase):
    def test_exact_summary_replay(self):
        self.assertEqual(audit_module().audit(), json.loads((HERE / 'summary.json').read_text()))

    def test_numeric_nonnumeric_balance_within_labels_and_languages(self):
        cases = json.loads((HERE / 'cases.json').read_text())['cases']
        for category in ('sufficient', 'related_insufficient', 'missing'):
            for language in ('en', 'zh'):
                selected = [c for c in cases if c['category'] == category and c['language'] == language]
                self.assertEqual(sorted(c['answer_kind'] for c in selected), ['nonnumeric', 'numeric'])

    def test_diagnostic_changes_only_the_unique_value(self):
        cases = json.loads((HERE / 'cases.json').read_text())['diagnostics']
        for language in ('en', 'zh'):
            full, removed = [c for c in cases if c['language'] == language]
            self.assertEqual(full['query'], removed['query'])
            before, after = full['context'][0]['text'], removed['context'][0]['text']
            self.assertEqual(before.count('500_000'), 1)
            self.assertEqual(before.replace('500_000', '', 1), after)
            self.assertNotIn('500000', after)
            self.assertIn('1_000', after)

    def test_errors_not_reported_as_correct_or_false_semantic_stops(self):
        result = audit_module().audit()['summary']
        self.assertEqual(result['additional_correct_evidence_stops'], 0)
        self.assertEqual(result['additional_false_evidence_stops'], 0)
        self.assertEqual(result['gate_protocol_failures_on_sufficient'], 4)
        self.assertEqual(result['existing_no_context_exits_excluded'], 2)

    def test_tampered_raw_record_is_detected(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / 'copy'
            shutil.copytree(HERE, target, ignore=shutil.ignore_patterns('__pycache__'))
            (target / 'recorded/d01-en-full.json').write_text('{}')
            with self.assertRaisesRegex(ValueError, 'recorded file changed'):
                audit_module().audit(target)

    def test_cli_offline_json(self):
        response = subprocess.run([sys.executable, str(HERE / 'audit_record.py')],
                                  check=True, capture_output=True, text=True, timeout=10)
        self.assertEqual(json.loads(response.stdout)['record_integrity'], 'verified')


if __name__ == '__main__':
    unittest.main()
