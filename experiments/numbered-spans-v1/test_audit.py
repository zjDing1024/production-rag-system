import hashlib
import json
from pathlib import Path
import shutil
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

    def alter(self, filename, modify):
        path = self.folder / filename
        value = json.loads(path.read_text())
        modify(value)
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')

    def test_archive_replays(self):
        self.assertEqual(audit(self.folder), json.loads((HERE / 'summary.json').read_text()))

    def test_fixture_mutation_fails(self):
        self.alter('cases.json', lambda value: value['cases'][0].update(query='different'))
        with self.assertRaisesRegex(ValueError, 'fixture hash'):
            audit(self.folder)

    def test_raw_mutation_fails(self):
        path = next((self.folder / 'recorded').glob('*.result.json'))
        path.write_text(path.read_text() + ' ')
        with self.assertRaisesRegex(ValueError, 'record hash'):
            audit(self.folder)

    def test_missing_record_fails(self):
        next((self.folder / 'recorded').glob('*.request.json')).unlink()
        with self.assertRaisesRegex(ValueError, 'archive file list'):
            audit(self.folder)

    def test_impossible_correct_annotation_fails(self):
        self.alter('assistant-review.json', lambda value: value['rows'][0].update(
            accepted_answer_supported_correct=True))
        with self.assertRaisesRegex(ValueError, 'impossible accepted correct'):
            audit(self.folder)

    def test_self_consistent_rehashed_wrong_prompt_fails(self):
        record = self.folder / 'recorded'
        manifest = json.loads((record / 'manifest.json').read_text())
        item = manifest['attempts'][0]
        path = record / item['request_file']
        payload = json.loads(path.read_text())
        payload['messages'][1]['content'] = 'injected answer metadata'
        path.write_text(json.dumps(payload) + '\n')
        item['request_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
        (record / 'manifest.json').write_text(json.dumps(manifest) + '\n')
        index = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in record.glob('*.json')}
        (self.folder / 'recorded-files.sha256.json').write_text(json.dumps(index) + '\n')
        with self.assertRaisesRegex(ValueError, 'recorded prompt differs'):
            audit(self.folder)


if __name__ == '__main__':
    unittest.main()
