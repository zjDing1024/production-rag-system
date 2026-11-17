import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from audit_record import HERE, audit


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name) / 'experiment'
        shutil.copytree(HERE, self.folder, ignore=shutil.ignore_patterns('__pycache__'))

    def alter(self, filename, modifier):
        path = self.folder / filename
        value = json.loads(path.read_text())
        modifier(value)
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')

    def test_archive_replays(self):
        self.assertEqual(audit(self.folder), json.loads((HERE / 'summary.json').read_text()))

    def test_fixture_mutation_detected(self):
        self.alter('cases.json', lambda value: value['cases'][0].update(query='different'))
        with self.assertRaisesRegex(ValueError, 'fixture not frozen or hash changed'):
            audit(self.folder)

    def test_record_mutation_detected(self):
        path = next((self.folder / 'recorded').glob('*.result.json'))
        path.write_text(path.read_text() + ' ')
        with self.assertRaisesRegex(ValueError, 'record hash changed'):
            audit(self.folder)

    def test_missing_record_detected(self):
        next((self.folder / 'recorded').glob('*.request.json')).unlink()
        with self.assertRaisesRegex(ValueError, 'archive file list changed'):
            audit(self.folder)

    def test_wrong_subject_cannot_be_marked_supported(self):
        def modify(value):
            row = next(r for r in value['rows'] if r['case_id'] == 'r01-en-insufficient' and r['arm'] == 'branched')
            row['accepted_supported_correct'] = True
        self.alter('assistant-review.json', modify)
        with self.assertRaisesRegex(ValueError, 'impossible supported correct'):
            audit(self.folder)

    def test_rehashed_prompt_mutation_detected(self):
        record = self.folder / 'recorded'
        manifest = json.loads((record / 'manifest.json').read_text())
        entry = manifest['attempts'][0]
        path = record / entry['request_file']
        payload = json.loads(path.read_text())
        payload['messages'][1]['content'] = 'answer leaked outside evidence'
        path.write_text(json.dumps(payload) + '\n')
        entry['request_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
        (record / 'manifest.json').write_text(json.dumps(manifest) + '\n')
        (self.folder / 'recorded-files.sha256.json').write_text(json.dumps({
            p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in record.glob('*.json')}) + '\n')
        with self.assertRaisesRegex(ValueError, 'selector request mismatch'):
            audit(self.folder)

    def test_object_comparison_cli_outside_repository(self):
        result = subprocess.run([sys.executable, str(HERE / 'audit_record.py'), '--check'],
                                cwd=self.temp.name, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('summary matches', result.stdout)


if __name__ == '__main__':
    unittest.main()
