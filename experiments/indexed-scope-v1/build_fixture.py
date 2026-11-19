"""Original constructed BM25/claim-catalog controls; no private telemetry."""
from dataclasses import asdict
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src'))
from rag_foundation.corpus import Chunk, digest
from rag_foundation.scoped_pipeline import chunks_fingerprint
from rag_foundation.scope_gate import Scope

RUNTIME = Scope('runtime', 'Cedar', 'timeout_seconds', observed_at='2032-07-08T09:00:00Z')
ROUTE = Scope('runtime', 'Cedar', 'health_route', observed_at='2032-07-08T09:00:00Z')
DOC = Scope('documentation', 'Flask', 'SEND_FILE_MAX_AGE_DEFAULT', version='1.1.4')
NEW_DOC = Scope('documentation', 'Flask', 'SEND_FILE_MAX_AGE_DEFAULT', version='3.1.2')


def record(cid, text, scope, value=30, value_type='integer', unit='seconds', reviewed=True):
    text_hash = digest(text.encode())
    chunk = Chunk(cid, 'invented-' + cid, 'Original invented review fixture', text,
                  'synthetic://indexed-scope-v1/' + cid, text_hash, 'MIT', 0, len(text), 1, text.count('\n')+1)
    claim = {'reviewed': True, 'chunk_text_sha256': text_hash, 'value_type': value_type,
             'unit': unit, 'value': value, 'start_char': 0, 'end_char': len(text), 'quote': text} if reviewed else None
    return chunk, {'chunk_id': cid, 'scope': asdict(scope) if scope else None, 'claim': claim}


def case(cid, query, scope, records, reason, call, *, k=1, budget=12000, scan_limit=128, complete=True):
    chunks = [r[0] for r in records]
    return {'id': cid, 'request': {'query': query, 'scope': asdict(scope)},
            'chunks': [asdict(c) for c in chunks],
            'catalog': {'schema_version': 1, 'complete': complete, 'chunks_sha256': chunks_fingerprint(chunks),
                        'entries': [r[1] for r in records]},
            'options': {'k': k, 'context_characters': budget, 'scan_limit': scan_limit},
            'expected': {'scoped_reason': reason, 'scoped_generator_called': call},
            'data_boundary': 'Original synthetic review fixtures; no real runtime telemetry; doc facts are original paraphrases of pinned public sources.'}


def build():
    cases = []
    for lang, query, hidden in (
        ('en', 'What is Cedar cache timeout policy at 2032-07-08T09:00:00Z?', 'The configured duration is VALUE seconds.'),
        ('zh', 'Cedar 在 2032-07-08T09:00:00Z 的 timeout policy 是多少秒？', '等待时长为VALUE秒。')):
        hot = record('h7', 'Cedar cache timeout policy: 30 seconds.', RUNTIME)
        for label, value, word in [('agreement', 30, 'thirty' if lang=='en' else '三十'), ('conflict',90,'ninety' if lang=='en' else '九十')]:
            cold = record('z2', hidden.replace('VALUE',word), RUNTIME, value)
            cases.append(case(f'zero-{lang}-{label}', query, RUNTIME, [hot,cold], 'contract_valid' if label=='agreement' else 'reviewed_value_conflict', label=='agreement'))
    # Non-numeric claims and a lexical-zero same-scope path conflict.
    for label, value in [('agreement','/ready-new'),('conflict','/ready-old')]:
        records = [record('h7','Cedar health route status: /ready-new.', ROUTE,'/ready-new','string','path'),
                   record('z2','入口配置为 '+value+'。',ROUTE,value,'string','path')]
        cases.append(case('path-'+label, 'What is Cedar health route status at 2032-07-08T09:00:00Z?', ROUTE,records,
                          'contract_valid' if label=='agreement' else 'reviewed_value_conflict',label=='agreement'))
    # Same scores/tie, independent ID assignment and source order. Conflict always pre-rank.
    for order in (0,1):
        for mapping in (0,1):
            ids = ('a1','b9') if not mapping else ('b9','a1')
            records = [record(ids[0],'cache timeout: 30 seconds.',RUNTIME,30),record(ids[1],'cache timeout: 90 seconds.',RUNTIME,90)]
            if order:records.reverse()
            cases.append(case(f'tie-o{order}i{mapping}','cache timeout',RUNTIME,records,'reviewed_value_conflict',False))
    hot=record('h7','Cedar cache timeout policy: 30 seconds.',RUNTIME)
    cases.extend([
        case('missing-review','cache timeout policy',RUNTIME,[hot,record('z2','The duration is uncertain.',RUNTIME,reviewed=False)],'missing_reviewed_claim',False),
        case('incomparable-unit','cache timeout policy',RUNTIME,[hot,record('z2','Thirty minutes are configured.',RUNTIME,30,unit='minutes')],'incomparable_claims',False),
        case('unassigned-scope','cache timeout policy',RUNTIME,[hot,record('z2','The duration is ninety seconds.',None,90)],'catalog_incomplete',False),
        case('declared-incomplete','cache timeout policy',RUNTIME,[hot],'catalog_incomplete',False,complete=False),
        case('scan-limit','cache timeout policy',RUNTIME,[hot,record('z2','The duration is thirty seconds.',RUNTIME)],'scope_scan_limit',False,scan_limit=1),
        case('context-budget','cache timeout policy',RUNTIME,[hot],'context_budget_exhausted',False,budget=1),
        case('no-match','cache timeout policy',ROUTE,[hot],'no_matching_scope',False),
        case('no-lexical','unseen_token_x',RUNTIME,[hot],'no_lexical_candidates',False),
        case('partial-packing','cache timeout policy',RUNTIME,[hot,record('z2','cache timeout policy duration: 30 seconds.',RUNTIME)],'contract_valid',True,k=2,budget=len(hot[0].text)),
    ])
    # Version facts from existing pinned source receipts, not upstream copied text.
    old=record('good','The Flask 1.1.4 documented SEND_FILE_MAX_AGE_DEFAULT default is 43200 seconds.',DOC,43200)
    wrong=record('wrong','SEND_FILE_MAX_AGE_DEFAULT default default default: None for Flask 3.1.2.',NEW_DOC,None,'null','configuration')
    cases.append(case('wrong-version-before-topk','SEND_FILE_MAX_AGE_DEFAULT default',DOC,[wrong,old],'contract_valid',True))
    # Literal null is reviewed evidence, different from claim:null (unreviewed).
    cases.append(case('literal-null','SEND_FILE_MAX_AGE_DEFAULT default',NEW_DOC,[wrong,old],'contract_valid',True))
    # Post-top-k filter counterexample: eligible record has overlap but loses top-1.
    records=[record('x1','cache timeout policy; health route: /a.',ROUTE,'/a','string','path'),
             record('x2','cache timeout policy cache timeout policy; health route: /a.',ROUTE,'/a','string','path'),
             record('x3','cache timeout policy cache timeout policy cache timeout policy; health route: /a.',ROUTE,'/a','string','path'),
             record('ok','cache timeout policy: 30 seconds. '+('neutral '*20),RUNTIME)]
    cases.append(case('eligibility-before-topk','cache timeout policy',RUNTIME,records,'contract_valid',True))
    return {'schema_version':1,'study':'indexed-scope-v1','cases':cases}


if __name__=='__main__':
    from rag_foundation.corpus import canonical_json
    print(canonical_json(build()),end='')
