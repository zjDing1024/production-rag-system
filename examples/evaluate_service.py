"""Three disclosed ablations on the already-seen development set, not holdout."""
import json
from pathlib import Path
from rag_foundation.corpus import load_corpus, canonical_json, digest
from rag_foundation.evaluation import load_questions, is_relevant
from rag_foundation.service import RetrievalService

root = Path('.')
service = RetrievalService(root)
questions = load_questions(root / 'data/evaluation/questions.json', load_corpus(root))
chunks = {c.id: c for c in service.chunks}
report = {'scope': 'seen development set; glossary and gate not independently validated',
          'generator': None, 'question_sha256': digest((root / 'data/evaluation/questions.json').read_bytes()),
          'chunks_sha256': service.fingerprint, 'variants': {}}
for name, expansion, gate in [('baseline', False, False), ('glossary', True, False), ('glossary_gate', True, True)]:
    rows = []
    for q in questions:
        result = service.retrieve({'query': q['query'], 'expand_zh': expansion, 'gate': gate})
        hit = any(is_relevant(chunks[h['chunk_id']], q) for h in result['results'])
        rows.append({'id': q['id'], 'answerable': q['answerable'], 'hit@5': hit,
                     'status': result['status'], 'coverage': result['policy']['coverage'],
                     'missing_terms': result['policy']['missing_terms'],
                     'chunk_ids': [h['chunk_id'] for h in result['results']]})
    positives = [r for r in rows if r['answerable']]
    negatives = [r for r in rows if not r['answerable']]
    report['variants'][name] = {'hit@5': sum(r['hit@5'] for r in positives) / len(positives),
        'answerable_abstained': sum(r['status'] == 'abstained' for r in positives),
        'unanswerable_nonempty': sum(r['status'] == 'candidates' for r in negatives), 'rows': rows}
print(canonical_json(report), end='')
