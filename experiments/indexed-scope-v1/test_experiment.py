import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parent))
from audit_record import audit, audit_correction
from build_fixture import build
from build_english_correction import build_correction
from run_experiment import HERE, execute, sha
from rag_foundation.retrieval import tokenize


class RecordedIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.cases={c['id']:c for c in build()['cases']}

    def test_cases_match_frozen_build(self):
        self.assertEqual(json.loads((HERE/'cases.json').read_text()),build())

    def test_original_pair_labels_and_known_english_discrepancy(self):
        for prefix in ('zero-en','zero-zh','path'):
            a=self.cases[prefix+'-agreement'];b=self.cases[prefix+'-conflict']
            self.assertEqual(a['request'],b['request']);self.assertEqual(a['chunks'][0],b['chunks'][0])
            self.assertEqual(len(a['chunks'][1]['text']),len(b['chunks'][1]['text']))
            for c in (a,b):
                overlap=set(tokenize(c['request']['query'])) & set(tokenize(c['chunks'][1]['text']))
                self.assertEqual(overlap, {'is'} if prefix=='zero-en' else set())
                self.assertEqual(c['options']['k'],1)

    def test_english_correction_genuinely_zero_overlap(self):
        fixture=build_correction()
        self.assertEqual(fixture,json.loads((HERE/'english-correction/cases.json').read_text()))
        original=json.loads((HERE/'initial-input-check.json').read_text())
        self.assertEqual(original['failed_tests'],1)
        for c in fixture['cases']:
            self.assertFalse(set(tokenize(c['request']['query'])) & set(tokenize(c['chunks'][1]['text'])))
        r=execute(HERE/'english-correction')
        for row in r['rows']:
            self.assertEqual([h['chunk_id'] for h in row['diagnostic_full_scores']],['h7'])
        self.assertEqual(r['rows'][0]['arms']['scoped']['result']['reason'],'contract_valid')
        self.assertEqual(r['rows'][1]['arms']['scoped']['result']['reason'],'reviewed_value_conflict')

    def test_paired_baseline_contexts_are_identical(self):
        rows={r['case_id']:r for r in execute()['rows']}
        for prefix in ('zero-en','zero-zh','path'):
            a=rows[prefix+'-agreement'];b=rows[prefix+'-conflict']
            self.assertEqual(a['arms']['ungated']['result']['context'],b['arms']['ungated']['result']['context'])
            self.assertTrue(a['arms']['scoped']['result']['generator_called'])
            self.assertFalse(b['arms']['scoped']['result']['generator_called'])
        corrected=execute(HERE/'english-correction')['rows']
        self.assertEqual(corrected[0]['arms']['ungated']['result']['context'],corrected[1]['arms']['ungated']['result']['context'])

    def test_correction_replay(self):
        self.assertEqual(audit_correction(),json.loads((HERE/'english-correction/summary.json').read_text()))

    def test_actual_saved_scope_outcomes_and_callback_counts(self):
        record=execute();rows={r['case_id']:r for r in record['rows']}
        self.assertEqual(len(rows),22)
        for r in rows.values():
            scoped=r['arms']['scoped'];self.assertEqual(scoped['real_model_calls'],0)
            self.assertEqual(len(scoped['spy_calls']),int(scoped['result']['generator_called']))
            if scoped['result']['reason'] in ('reviewed_value_conflict','missing_reviewed_claim','scope_scan_limit','catalog_incomplete','incomparable_claims'):
                self.assertIsNone(scoped['result']['ranking']);self.assertEqual(scoped['spy_calls'],[])
        rescued=rows['eligibility-before-topk']
        self.assertEqual(rescued['post_topk_scope_ids'],[]);self.assertEqual(rescued['eligible_before_topk_ids'],['ok'])
        self.assertEqual(rows['literal-null']['arms']['scoped']['result']['preflight']['status'],'consistent')

    def test_order_id_conflict_invariance(self):
        rows={r['case_id']:r for r in execute()['rows']}
        for o in (0,1):
            for i in (0,1):
                self.assertEqual(rows[f'tie-o{o}i{i}']['arms']['scoped']['result']['reason'],'reviewed_value_conflict')

    def test_replay_exact_summary(self):
        self.assertEqual(audit(),json.loads((HERE/'summary.json').read_text()))

    def temp_copy(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        folder=Path(tmp.name)/'record';shutil.copytree(HERE,folder,ignore=shutil.ignore_patterns('__pycache__'));return folder

    def test_changed_record_rejected(self):
        d=self.temp_copy();p=d/'recorded.json';p.write_text(p.read_text()+' ')
        with self.assertRaisesRegex(ValueError,'checksum'):audit(d)

    def test_rehashed_wrong_route_rejected(self):
        d=self.temp_copy();p=d/'recorded.json';x=json.loads(p.read_text());x['rows'][0]['arms']['scoped']['result']['reason']='changed';p.write_text(json.dumps(x))
        (d/'recorded.sha256.json').write_text(json.dumps({'recorded.json':sha(p)}))
        with self.assertRaisesRegex(ValueError,'pipeline replay'):audit(d)

    def test_changed_fixture_rejected(self):
        d=self.temp_copy();p=d/'cases.json';p.write_text(p.read_text()+' ')
        with self.assertRaisesRegex(ValueError,'fixture changed'):audit(d)

    def test_check_outside_repository(self):
        with tempfile.TemporaryDirectory() as d:
            result=subprocess.run([sys.executable,str(HERE/'audit_record.py'),'--check'],cwd=d,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)


if __name__=='__main__':unittest.main()
