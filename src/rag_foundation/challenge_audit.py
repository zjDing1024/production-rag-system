"""Post-run v1 evidence audit: preserve original report, disambiguate a02."""
import json
from pathlib import Path

from .challenge import load_challenge
from .corpus import canonical_json, digest
from .evaluation import normalize_space
from .service import RetrievalService

# Versioned post-run correction, not silently substituted into frozen v1 labels.
A02_ANCHOR = '''.. py:data:: MAX_CONTENT_LENGTH

    The maximum number of bytes that will be read during this request. If
    this limit is exceeded, a 413 :exc:`~werkzeug.exceptions.RequestEntityTooLarge`
    error is raised.'''


def anchored_a02(chunk):
    return chunk.document_id == 'flask-config' and normalize_space(A02_ANCHOR) in normalize_space(chunk.text)


def audit(root):
    load_challenge(root)  # Verify frozen inputs and labels before auditing.
    path = root / 'results/bilingual-challenge-v1.json'
    original = json.loads(path.read_text())
    service = RetrievalService(root)
    chunks = {c.id: c for c in service.chunks}
    variants = {}
    for name, variant in original['variants'].items():
        rows = []
        for row in variant['rows']:
            if row['category'] != 'answerable':
                continue
            matching = [h['chunk_id'] for h in row['results'] if anchored_a02(chunks[h['chunk_id']])]
            hit = bool(matching) if row['pair_id'] == 'a02' else row['answer_evidence_hit']
            rows.append({'id': row['id'], 'language': row['language'],
                         'original_hit': row['answer_evidence_hit'], 'audited_hit': hit,
                         'corrected_a02_chunk_ids': matching if row['pair_id'] == 'a02' else None})
        variants[name] = {'rows': rows, 'groups': {
            lang: {'count': len(group), 'hits': sum(r['audited_hit'] for r in group)}
            for lang in ('all', 'en', 'zh')
            for group in [[r for r in rows if lang == 'all' or r['language'] == lang]]}}
    return {'schema_version': 1, 'audit_version': 'a02-section-anchor-v1',
            'timing': 'Post-first-run correction; original frozen labels and result retained unchanged',
            'reason': 'a02 quote repeats under three config fields; require MAX_CONTENT_LENGTH heading plus contiguous definition and 413 sentence',
            'original_result_sha256': digest(path.read_bytes()),
            'suite_sha256': original['freeze']['suite_sha256'],
            'anchor': A02_ANCHOR, 'variants': variants}


if __name__ == '__main__':
    print(canonical_json(audit(Path('.'))), end='')
