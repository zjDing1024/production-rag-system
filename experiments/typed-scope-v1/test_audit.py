import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parent))
from audit_record import HERE,audit
from verify_sources import verify


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.folder=Path(self.tmp.name)/'record';shutil.copytree(HERE,self.folder,ignore=shutil.ignore_patterns('__pycache__'))

    def change(self,name,modifier):
        p=self.folder/name;x=json.loads(p.read_text());modifier(x);p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')

    def test_full_replay(self):
        self.assertEqual(audit(self.folder),json.loads((HERE/'summary.json').read_text()))

    def test_changed_fixture_fails(self):
        self.change('cases.json',lambda x:x['cases'][0]['input'].update(query='different'))
        with self.assertRaisesRegex(ValueError,'fixture hash changed'):audit(self.folder)

    def test_changed_record_fails(self):
        p=next((self.folder/'recorded').glob('*.result.json'));p.write_text(p.read_text()+' ')
        with self.assertRaisesRegex(ValueError,'record hash changed'):audit(self.folder)

    def test_missing_record_fails(self):
        next((self.folder/'recorded').glob('*.result.json')).unlink()
        with self.assertRaisesRegex(ValueError,'archive file list changed'):audit(self.folder)

    def test_negative_value_match_cannot_be_correct(self):
        def change(x):
            row=next(r for r in x['rows'] if r['arm']=='ungated' and r['case_id'].endswith('insufficient'))
            row['answer_value_correct']=True
        self.change('assistant-review.json',change)
        with self.assertRaisesRegex(ValueError,'impossible value-correct'):audit(self.folder)

    def test_rehashed_wire_tamper_fails(self):
        record=self.folder/'recorded';manifest=json.loads((record/'manifest.json').read_text());e=manifest['attempts'][0]
        p=record/e['result_file'];x=json.loads(p.read_text());x['arms']['ungated']['request']['messages'][0]['content']='changed prompt'
        p.write_text(json.dumps(x)+'\n');e['result_sha256']=hashlib.sha256(p.read_bytes()).hexdigest();(record/'manifest.json').write_text(json.dumps(manifest)+'\n')
        (self.folder/'recorded-files.sha256.json').write_text(json.dumps({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in record.glob('*.json')})+'\n')
        with self.assertRaisesRegex(ValueError,'wire request mismatch'):audit(self.folder)

    def test_check_cli_outside_repository(self):
        result=subprocess.run([sys.executable,str(HERE/'audit_record.py'),'--check'],cwd=self.tmp.name,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_source_default_no_network(self):
        from unittest.mock import patch
        with patch('urllib.request.urlopen',side_effect=AssertionError('network forbidden')):
            result=verify(False)
        self.assertEqual([r['status'] for r in result['source_checks']],['not_fetched','not_fetched','verified_existing_local_corpus'])


if __name__=='__main__':unittest.main()
