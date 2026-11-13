from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from rag_foundation.challenge import evaluate_challenge, load_challenge, summarize, validate_questions
from rag_foundation.corpus import load_corpus
from rag_foundation.challenge_audit import audit, anchored_a02, A02_ANCHOR
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]


class ChallengeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload, cls.lock = load_challenge(ROOT)
        cls.documents = load_corpus(ROOT)

    def test_frozen_inputs_and_pairs(self):
        self.assertEqual(len(self.payload['questions']), 24)
        self.assertEqual(len({q['pair_id'] for q in self.payload['questions']}), 12)
        validate_questions(self.payload, self.documents)

    def test_changed_suite_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / 'data/evaluation'
            target.mkdir(parents=True)
            (target / 'bilingual-challenge-v1.lock.json').write_text(json.dumps(self.lock))
            (target / 'bilingual-challenge-v1.json').write_text('{}')
            with self.assertRaisesRegex(ValueError, 'frozen input changed: suite_sha256'):
                load_challenge(root)

    def test_duplicate_id_rejected(self):
        payload = deepcopy(self.payload)
        payload['questions'][1]['id'] = payload['questions'][0]['id']
        with self.assertRaises(ValueError):
            validate_questions(payload, self.documents)

    def test_invented_quote_rejected(self):
        payload = deepcopy(self.payload)
        payload['questions'][0]['evidence'][0]['quote'] = 'invented undocumented evidence'
        with self.assertRaisesRegex(ValueError, 'quote not found'):
            validate_questions(payload, self.documents)

    def test_pair_mismatch_rejected(self):
        payload = deepcopy(self.payload)
        payload['questions'][1]['language'] = 'en'
        with self.assertRaisesRegex(ValueError, 'one en and one zh'):
            validate_questions(payload, self.documents)

    def test_topic_hit_is_not_answer_hit(self):
        rows = [dict(category='related_insufficient', language='en', status='candidates',
                     topic_evidence_hit=True, answer_evidence_hit=False),
                dict(category='answerable', language='en', status='abstained',
                     topic_evidence_hit=False, answer_evidence_hit=False)]
        groups = summarize(rows)
        self.assertEqual(groups['related_insufficient/en']['insufficient_admission_count'], 1)
        self.assertIsNone(groups['related_insufficient/en']['hit@5'])
        self.assertEqual(groups['answerable/en']['hit@5'], 0.0)
        self.assertEqual(groups['answerable/en']['abstained'], 1)
        self.assertIsNone(groups['missing/en']['insufficient_admission_rate'])

    def test_anchor_rejects_wrong_configuration_field(self):
        correct = SimpleNamespace(document_id='flask-config', text=A02_ANCHOR)
        wrong = SimpleNamespace(document_id='flask-config', text=A02_ANCHOR.replace('MAX_CONTENT_LENGTH', 'MAX_FORM_PARTS'))
        self.assertTrue(anchored_a02(correct))
        self.assertFalse(anchored_a02(wrong))

    def test_postrun_audit_reproduces(self):
        expected = json.loads((ROOT / 'results/bilingual-challenge-v1-audit.json').read_text())
        self.assertEqual(audit(ROOT), expected)

    def test_report_reproduces(self):
        actual = evaluate_challenge(ROOT)
        expected = json.loads((ROOT / 'results/bilingual-challenge-v1.json').read_text())
        self.assertEqual(actual, expected)
        for variant in actual['variants'].values():
            self.assertEqual(len(variant['rows']), 24)
            self.assertTrue(all(r['answer'] is None for r in variant['rows']))
            for category in ('answerable', 'related_insufficient', 'missing'):
                self.assertEqual(variant['groups'][category + '/all']['count'], 8)


if __name__ == '__main__':
    unittest.main()
