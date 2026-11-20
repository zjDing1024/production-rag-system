"""Model-free fixed lexical and scope coverage, frozen before model calls."""
from pathlib import Path
import json
from adapter import run_case,make_pipeline
from rag_foundation.corpus import canonical_json
from rag_foundation.retrieval import BM25
HERE=Path(__file__).resolve().parent


def preflight():
    rows=[]
    for c in json.loads((HERE/'cases.json').read_text())['cases']:
        p=make_pipeline(c);full=BM25(list(p.index.chunks)).search(c['request']['query'],len(c['chunks']))
        plans={a:run_case(c,a) for a in ('ungated','scoped')}
        assert plans['ungated']['context'],(c['id'],'negative must exercise model, not lexical zero')
        assert bool(plans['scoped']['context'])==c['rubric']['offered_sufficient']
        for a,result in plans.items():
            for hit in result['context']:
                assert hit['score']==next(h.score for h in full if h.chunk.id==hit['chunk_id'])
        rows.append({'case_id':c['id'],'full_scores':[{'chunk_id':h.chunk.id,'score':h.score} for h in full],
                     'plans':plans,'offered_sufficient':c['rubric']['offered_sufficient'],
                     'packed_support':{a:all(i in [h['chunk_id'] for h in r['context']] for i in c['rubric']['supporting_ids']) and bool(c['rubric']['supporting_ids']) for a,r in plans.items()}})
    return {'scope':'actual project BM25 and deterministic preflight, no model',
            'expected_model_calls':sum(bool(p['context']) for r in rows for p in r['plans'].values()),'rows':rows}


if __name__=='__main__':print(canonical_json(preflight()),end='')
