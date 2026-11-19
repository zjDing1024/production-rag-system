"""Execute real BM25 and pipeline with a disclosed non-model generator spy."""
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
sys.path.insert(0,str(REPO/'src'))
from rag_foundation.corpus import Chunk, canonical_json
from rag_foundation.generation import strict_json, validate_answer
from rag_foundation.retrieval import BM25
from rag_foundation.scope_gate import Scope
from rag_foundation.scoped_pipeline import ClaimIndex, ScopedGenerationPipeline


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class RecordingSpy:
    """Contract fixture only. Does not read labels or extract any answer value."""
    def __init__(self):self.calls=[]
    def generate(self,query,context):
        self.calls.append({'query':query,'chunk_ids':[h['chunk_id'] for h in context]})
        value={'answer':'CONTRACT FIXTURE ONLY; NO MODEL INFERENCE',
               'citations':[context[0]['chunk_id']],'abstain':False}
        validate_answer(value,[h['chunk_id'] for h in context])
        return {'status':'answered','reason':'contract_valid','answer':value['answer'],
                'citation_ids':value['citations'],'raw_response':None,
                'producer':'deterministic_recording_spy_not_a_model'}


def verify_freeze(directory=HERE):
    lock=strict_json((directory/'freeze.json').read_text(encoding='utf-8'))
    if lock['status']!='frozen_before_recorded_run':raise ValueError('not frozen')
    for name,expected in lock['sha256'].items():
        if sha(REPO/name)!=expected:raise ValueError('frozen file changed: '+name)
    return lock


def execute(directory=HERE):
    lock=verify_freeze(directory)
    fixture=strict_json((directory/'cases.json').read_text(encoding='utf-8'))
    rows=[]
    for case in fixture['cases']:
        chunks=[Chunk(**c) for c in case['chunks']];idx=ClaimIndex(chunks,case['catalog'])
        query=case['request']['query'];scope=Scope.from_dict(case['request']['scope']);arms={}
        for name,enabled in (('ungated',False),('scoped',True)):
            spy=RecordingSpy();result=ScopedGenerationPipeline(idx,spy).answer(query,scope,scope_gate=enabled,**case['options'])
            if len(spy.calls)!=int(result['generator_called']):raise AssertionError('callback accounting mismatch')
            arms[name]={'result':result,'spy_calls':spy.calls,'real_model_calls':0}
        expected=case['expected']
        if (arms['scoped']['result']['reason']!=expected['scoped_reason'] or
                arms['scoped']['result']['generator_called']!=expected['scoped_generator_called']):
            raise AssertionError('prespecified routing mismatch: '+case['id'])
        # Independent diagnostic after both pipelines: old scorer over identical
        # full index. This does not supply candidates or labels to the pipeline.
        full=BM25(chunks).search(query,len(chunks))
        full_scores={h.chunk.id:h.score for h in full}
        eligible={c.id for c in chunks if idx.scopes.get(c.id)==scope}
        eligible_hits=idx.bm25.search(query,len(chunks),eligible_ids=eligible)
        equal=all(full_scores[h.chunk.id]==h.score for h in eligible_hits)
        if not equal:raise AssertionError('filtered scores changed')
        rows.append({'case_id':case['id'],'arms':arms,
                     'diagnostic_full_scores':[{'chunk_id':h.chunk.id,'score':h.score} for h in full],
                     'post_topk_scope_ids':[h.chunk.id for h in full[:case['options']['k']] if h.chunk.id in eligible],
                     'eligible_before_topk_ids':[h.chunk.id for h in eligible_hits[:case['options']['k']]],
                     'eligible_score_comparisons':len(eligible_hits),
                     'all_filtered_scores_exact':equal,'expected_route_matched':True})
    return {'schema_version':1,'execution':'real_project_BM25_and_pipeline_with_non_model_spy',
            'freeze_sha256':sha(directory/'freeze.json'),'frozen_files':lock['sha256'],
            'real_model_calls':0,'rows':rows}


def summarize(record):
    from collections import Counter
    arms={}
    for arm in ('ungated','scoped'):
        rr=[r['arms'][arm] for r in record['rows']]
        arms[arm]={'offered_cases':len(rr),'spy_calls':sum(len(r['spy_calls']) for r in rr),
                   'real_model_calls':0,'reason_counts':dict(sorted(Counter(r['result']['reason'] for r in rr).items())),
                   'status_counts':dict(sorted(Counter(r['result']['status'] for r in rr).items()))}
    return {'study':'indexed-scope-v1','scope':'mechanism evidence, not model answer accuracy',
            'expected_routing_matches':sum(r['expected_route_matched'] for r in record['rows']),
            'score_equality_cases':sum(r['all_filtered_scores_exact'] for r in record['rows']),
            'nonempty_score_equality_cases':sum(r['eligible_score_comparisons']>0 for r in record['rows']),
            'individual_exact_score_comparisons':sum(r['eligible_score_comparisons'] for r in record['rows']),
            'arms':arms}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True,help='new output JSON; never overwrite evidence')
    args=parser.parse_args()
    result=execute()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf-8') as stream:stream.write(canonical_json(result))
    print(canonical_json(summarize(result)),end='')
