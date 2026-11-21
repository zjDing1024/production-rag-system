"""Offline paired replay over the prior public Express/CPython summaries."""
import argparse
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / 'src'))

from rag_foundation.corpus import Chunk, canonical_json
from rag_foundation.scope_gate import Scope
from rag_foundation.scoped_pipeline import ClaimIndex, ScopedGenerationPipeline, chunks_fingerprint
from rag_foundation.version_bound import answer_with_version_binding

INPUT = REPO / 'experiments' / 'source-transfer-v1' / 'cases.json'


def slice_case(row, first_only=False):
    limit = 1 if first_only else len(row['chunks'])
    return [Chunk(**item) for item in row['chunks'][:limit]], row['catalog']['entries'][:limit]


def build_index(chunks, entries):
    return ClaimIndex(chunks, {'schema_version': 1, 'complete': True,
                               'chunks_sha256': chunks_fingerprint(chunks), 'entries': entries})


def project(outcome):
    return {'status': outcome['status'], 'reason': outcome['reason'],
            'generator_called': outcome['generator_called'],
            'packed_ids': [h['chunk_id'] for h in outcome['context']],
            'ranking_performed': outcome['ranking'] is not None}


def compare(pipeline, query, scope):
    legacy = pipeline.answer(query, scope, k=1, scope_gate=True)
    guarded = answer_with_version_binding(pipeline, query, scope, k=1)
    bound_outcome = guarded['pipeline']
    return {'unbound': project(legacy),
            'bound': project(bound_outcome) if bound_outcome is not None else {
                'status': guarded['status'], 'reason': guarded['reason'],
                'generator_called': guarded['generator_called'], 'packed_ids': [],
                'ranking_performed': False},
            'observations': guarded['binding']['observations']}


def replay():
    cases = {row['id']: row for row in json.loads(INPUT.read_text(encoding='utf-8'))['cases']}
    positive_ids = {'4.21.2': 'e4default', '5.1.0': 'e5default'}
    older = cases['express-old-supported-en']
    newer = cases['express-new-supported-en']
    chunks, entries = slice_case(older)
    cross = []
    for lang in ('en', 'zh'):
        for original in ('old', 'new'):
            request = cases[f'express-{original}-supported-{lang}']['request']
            intended = request['scope']['version']
            query = request['query']
            for choice in (older, newer):
                scope = Scope.from_dict(choice['request']['scope'])
                pair = compare(ScopedGenerationPipeline(build_index(chunks, entries)), query, scope)
                cross.append({'language': lang, 'question': query, 'question_release': intended,
                              'scope_release': scope.version, 'matched_release': intended == scope.version,
                              'supporting_id': positive_ids[intended], **pair})
    controls = []
    for label in ('positive', 'older_only', 'explicit_only'):
        source_name = {'positive': 'express-new-supported-en', 'older_only': 'express-new-older-only-en',
                       'explicit_only': 'express-new-explicit-only-en'}[label]
        control_chunks, control_entries = slice_case(cases[source_name])
        if label == 'explicit_only':
            assignment_modes = ('complete',)
        else:
            assignment_modes = ('complete', 'extra_assigned', 'extra_unassigned')
        extra_chunks, extra_entries = slice_case(cases['py-default-near-field-en'], first_only=True)
        query, scope = newer['request']['query'], Scope.from_dict(newer['request']['scope'])
        for assignment in assignment_modes:
            pool = control_chunks if assignment == 'complete' else control_chunks + extra_chunks
            catalog = control_entries + extra_entries if assignment == 'extra_assigned' else control_entries
            pair = compare(ScopedGenerationPipeline(build_index(pool, catalog)), query, scope)
            controls.append({'control': label, 'assignment': assignment, **pair})
    rows = cross + controls
    return {
        'mode': 'actual_bm25_and_index_no_model', 'historical_input': str(INPUT.relative_to(REPO)),
        'request_top_k': 1, 'crossed_rows': cross, 'catalog_control_rows': controls,
        'metrics': {
            'matched_release_rows': sum(r['matched_release'] for r in cross),
            'crossed_release_rows': sum(not r['matched_release'] for r in cross),
            'matched_supported_unbound': sum(r['matched_release'] and r['unbound']['packed_ids'] == [r['supporting_id']] for r in cross),
            'matched_supported_bound': sum(r['matched_release'] and r['bound']['packed_ids'] == [r['supporting_id']] for r in cross),
            'crossed_wrong_release_packed_unbound': sum(not r['matched_release'] and bool(r['unbound']['packed_ids']) and r['unbound']['packed_ids'] != [r['supporting_id']] for r in cross),
            'crossed_stopped_by_binding': sum(not r['matched_release'] and r['bound']['reason'] == 'question_scope_release_mismatch' for r in cross),
            'model_calls': sum(r[a]['generator_called'] for r in rows for a in ('unbound','bound')),
        },
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    rendered = canonical_json(replay())
    if args.check:
        if (HERE / 'report.json').read_bytes() != rendered.encode('utf-8'):
            raise ValueError('version binding offline report changed')
        print('Version binding offline replay matches recorded report.')
    else:
        print(rendered, end='')
