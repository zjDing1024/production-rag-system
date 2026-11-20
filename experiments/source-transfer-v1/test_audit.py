import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent))
from audit_record import HERE,audit,sha
from verify_sources import verify


class AuditTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.directory=Path(tmp.name)/'copy';shutil.copytree(HERE,self.directory,ignore=shutil.ignore_patterns('__pycache__'))

    def change(self,name,operation):
        p=self.directory/name;value=json.loads(p.read_text());operation(value);p.write_text(json.dumps(value))

    def test_full_offline_replay(self):
        self.assertEqual(audit(),json.loads((HERE/'summary.json').read_text()))

    def test_changed_fixture_rejected(self):
        p=self.directory/'cases.json';p.write_text(p.read_text()+' ')
        with self.assertRaisesRegex(ValueError,'fixture changed'):audit(self.directory)

    def test_changed_record_rejected(self):
        p=next((self.directory/'recorded').glob('*.result.json'));p.write_text(p.read_text()+' ')
        with self.assertRaisesRegex(ValueError,'record hash changed'):audit(self.directory)

    def test_rehashed_changed_wire_request_rejected(self):
        directory=self.directory;manifest=json.loads((directory/'recorded/manifest.json').read_text());entry=manifest['attempts'][0]
        p=directory/'recorded'/entry['result_file'];r=json.loads(p.read_text());r['arms']['ungated']['request']['messages'][0]['content']='modified prompt';p.write_text(json.dumps(r))
        entry['result_sha256']=sha(p);(directory/'recorded/manifest.json').write_text(json.dumps(manifest))
        (directory/'recorded.sha256.json').write_text(json.dumps({p.name:sha(p) for p in (directory/'recorded').glob('*.json')}))
        with self.assertRaisesRegex(ValueError,'wire request mismatch'):audit(directory)

    def test_missing_record_rejected(self):
        next((self.directory/'recorded').glob('*.result.json')).unlink()
        with self.assertRaisesRegex(ValueError,'archive file set changed'):audit(self.directory)

    def test_no_run_cannot_be_truth_correct(self):
        def modify(x):
            r=next(r for r in x['rows'] if r['content_kind']=='no_output');r.update(truth_correct=True,content_kind='factual')
        self.change('assistant-review.json',modify)
        with self.assertRaisesRegex(ValueError,'truth annotation without factual answer'):audit(self.directory)

    def test_support_cannot_use_external_oracle_without_packed_evidence(self):
        def modify(x):
            r=next(r for r in x['rows'] if r['case_id']=='express-new-older-only-en' and r['arm']=='ungated');r['cited_support']=True
        self.change('assistant-review.json',modify)
        with self.assertRaisesRegex(ValueError,'support without cited supplied evidence'):audit(self.directory)

    def test_none_ambiguity_does_not_remove_unsupported_branch_denominator(self):
        r=audit();s=r['summary']['ungated']
        self.assertEqual(s['negative_accepted_without_cited_support'],12)
        self.assertEqual(s['negative_accepted_unsupported_factual'],9)
        self.assertEqual(s['accepted_semantic_nonanswer'],4)
        self.assertEqual(s['legitimate_model_refusal'],0)
        self.assertEqual(r['summary']['scoped']['deterministic_negative_block'],12)
        self.assertEqual(sum(x['unsupported_to_block'] for x in r['matched']),12)
        self.assertEqual(sum(x['unsupported_factual_to_block'] for x in r['matched']),9)

    def test_default_source_verification_has_no_network(self):
        with patch('urllib.request.urlopen',side_effect=AssertionError('no network allowed')):
            r=verify()
        self.assertFalse(r['network_requested']);self.assertTrue(all(x['status']=='not_fetched' for x in r['source_checks']))

    def test_cli_outside_repository(self):
        with tempfile.TemporaryDirectory() as directory:
            result=subprocess.run([sys.executable,str(HERE/'audit_record.py'),'--check'],cwd=directory,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)


if __name__=='__main__':unittest.main()
