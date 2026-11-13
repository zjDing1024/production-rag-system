"""Frozen bilingual retrieval diagnostics; not generated-answer evaluation."""
import argparse
from collections import Counter
import json
from pathlib import Path

from .corpus import canonical_json, digest, load_corpus
from .evaluation import is_relevant, normalize_space
from .service import RetrievalService

CATEGORIES = ('answerable', 'related_insufficient', 'missing')
VARIANTS = {'baseline': (False, False), 'glossary': (True, False), 'deployed': (True, True)}


def load_challenge(root):
    directory = root / 'data/evaluation'
    lock = json.loads((directory / 'bilingual-challenge-v1.lock.json').read_text())
    paths = {'suite_sha256': directory / 'bilingual-challenge-v1.json',
             'service_sha256': root / 'src/rag_foundation/service.py',
             'retrieval_sha256': root / 'src/rag_foundation/retrieval.py',
             'manifest_sha256': root / 'data/manifest.json'}
    for key, path in paths.items():
        if digest(path.read_bytes()) != lock[key]:
            raise ValueError(f'frozen input changed: {key}')
    payload = json.loads(paths['suite_sha256'].read_text())
    validate_questions(payload, load_corpus(root))
    return payload, lock


def validate_questions(payload, documents):
    if payload.get('schema_version') != 1:
        raise ValueError('unknown challenge schema')
    questions = payload.get('questions')
    if not isinstance(questions, list) or not questions:
        raise ValueError('questions must be a nonempty list')
    texts = {d.id: normalize_space(d.text) for d in documents}
    ids, pairs = set(), {}
    for q in questions:
        if not isinstance(q['id'], str) or not q['id'] or q['id'] in ids:
            raise ValueError('question IDs must be unique nonempty strings')
        ids.add(q['id'])
        if not isinstance(q['query'], str) or not q['query'].strip():
            raise ValueError('query must be nonempty text')
        if q['language'] not in ('en', 'zh') or q['category'] not in CATEGORIES:
            raise ValueError('invalid category or language')
        if not isinstance(q['pair_id'], str) or not q['pair_id']:
            raise ValueError('pair ID required')
        if not isinstance(q['evidence'], list):
            raise ValueError('evidence must be a list')
        if (q['category'] == 'missing') != (not q['evidence']):
            raise ValueError('only missing category has no topic evidence')
        if q['category'] != 'answerable' and not q['rationale'].strip():
            raise ValueError('non-answerable rationale required')
        for e in q['evidence']:
            quote = normalize_space(e['quote'])
            if not quote or quote not in texts.get(e['document_id'], ''):
                raise ValueError('quote not found in pinned document')
        pairs.setdefault(q['pair_id'], []).append(q)
    for pair in pairs.values():
        if len(pair) != 2 or {q['language'] for q in pair} != {'en', 'zh'}:
            raise ValueError('each pair requires exactly one en and one zh')
        if pair[0]['category'] != pair[1]['category'] or pair[0]['evidence'] != pair[1]['evidence']:
            raise ValueError('paired category and evidence must agree')


def summarize(rows):
    """Keep answer evidence hits distinct from admission of insufficient evidence."""
    groups = {}
    for category in CATEGORIES:
        for language in ('all', 'en', 'zh'):
            selected = [r for r in rows if r['category'] == category
                        and (language == 'all' or r['language'] == language)]
            count = len(selected)
            admitted = sum(r['status'] == 'candidates' for r in selected)
            groups[f'{category}/{language}'] = {
                'count': count, 'admitted': admitted, 'abstained': count - admitted,
                # Topic hits for insufficient queries are intentionally NOT scored as answer hits.
                'evidence_hit_count': sum(r['answer_evidence_hit'] for r in selected)
                    if category == 'answerable' else None,
                'hit@5': sum(r['answer_evidence_hit'] for r in selected) / count
                    if category == 'answerable' and count else None,
                'insufficient_admission_count': admitted if category != 'answerable' else None,
                'insufficient_admission_rate': admitted / count
                    if category != 'answerable' and count else None,
            }
    return groups


def evaluate_challenge(root):
    payload, lock = load_challenge(root)
    service = RetrievalService(root)
    chunks = {c.id: c for c in service.chunks}
    reports = {}
    for variant, (expand_zh, gate) in VARIANTS.items():
        rows = []
        for q in payload['questions']:
            result = service.retrieve({'query': q['query'], 'k': 5,
                                       'expand_zh': expand_zh, 'gate': gate})
            topic_hit = any(is_relevant(chunks[h['chunk_id']], q) for h in result['results'])
            rows.append({'id': q['id'], 'pair_id': q['pair_id'], 'language': q['language'],
                         'category': q['category'], 'query': q['query'],
                         'status': result['status'], 'answer': result['answer'],
                         'answer_evidence_hit': q['category'] == 'answerable' and topic_hit,
                         'topic_evidence_hit': topic_hit, 'coverage': result['policy']['coverage'],
                         'untranslated_cjk': result['untranslated_cjk'],
                         'effective_query': result['effective_query'],
                         'aliases': result['aliases'], 'missing_terms': result['policy']['missing_terms'],
                         'candidate_count_before_gate': result['candidate_count_before_gate'],
                         'results': [{'chunk_id': h['chunk_id'], 'score': h['score'],
                                      'citation': h['citation']} for h in result['results']]})
        reports[variant] = {'config': {'expand_zh': expand_zh, 'gate': gate, 'k': 5},
                            'groups': summarize(rows), 'rows': rows}
    return {'schema_version': 1, 'scope': payload['scope'], 'generator': None,
            'metric_warning': 'Admission is returning candidates, not generating an incorrect answer. Topic overlap is not sufficient evidence.',
            'freeze': lock, 'chunks_sha256': service.fingerprint,
            'question_count': len(payload['questions']),
            'category_counts': dict(Counter(q['category'] for q in payload['questions'])),
            'variants': reports}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('.'))
    args = parser.parse_args()
    print(canonical_json(evaluate_challenge(args.root)), end='')


if __name__ == '__main__':
    main()
