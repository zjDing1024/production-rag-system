"""Offline raw-contract replay and separate truth/support/coverage accounting."""
from collections import Counter
import argparse
import json
from pathlib import Path
from unittest.mock import Mock,patch
from adapter import BranchedGenerator,run_case,expected_request
from preflight import preflight
from run_experiment import sha
from rag_foundation.generation import strict_json
from rag_foundation.corpus import canonical_json

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
ARMS=('ungated','scoped')


def read(path):return strict_json(path.read_text(encoding='utf-8'))
def require(ok,message):
    if not ok:raise ValueError(message)


def fake_connection(raw,status=200):
    conn,response=Mock(),Mock();response.status=status;response.read.return_value=raw.encode('utf-8');conn.getresponse.return_value=response;return conn


def parsed(raw):
    try:return strict_json(strict_json(raw)['choices'][0]['message']['content'])
    except (TypeError,ValueError,KeyError,IndexError):return None


def aggregate(rows):
    return {'offered_rows':len(rows),'offered_positive':sum(r['offered_sufficient'] for r in rows),
            'offered_negative':sum(not r['offered_sufficient'] for r in rows),
            'packed_support_rows':sum(r['packed_support'] for r in rows),
            'model_calls':sum(r['generator_called'] for r in rows),
            'status_counts':dict(sorted(Counter(r['status'] for r in rows).items())),
            'no_run_reasons':dict(sorted(Counter(r['reason'] for r in rows if not r['generator_called']).items())),
            **{key:sum(r[key] for r in rows) for key in (
                'accepted_truth_correct','accepted_grounded_correct','accepted_grounded_literal_exact',
                'accepted_correct_but_unsupported','accepted_incorrect_factual','accepted_unsupported_factual',
                'accepted_without_cited_support','negative_accepted_without_cited_support',
                'negative_accepted_unsupported_factual','accepted_semantic_nonanswer',
                'legitimate_model_refusal','false_model_refusal','deterministic_negative_block',
                'invalid_or_transport_failure')}}


def audit(directory=HERE):
    lock=read(directory/'cases.lock.json');require(lock['status']=='frozen_before_execution','not frozen')
    require(sha(directory/'cases.json')==lock['cases_sha256'],'fixture changed')
    for name,value in lock['file_sha256'].items():require(sha(REPO/name)==value,'frozen file changed: '+name)
    pf=preflight();require(pf==read(directory/'preflight.json'),'preflight changed')
    plans={r['case_id']:r for r in pf['rows']};cases=read(directory/'cases.json')['cases'];by_id={c['id']:c for c in cases}
    record=directory/'recorded';index=read(directory/'recorded.sha256.json')
    require(set(index)=={p.name for p in record.glob('*.json')},'archive file set changed')
    for name,value in index.items():require(Path(name).name==name and sha(record/name)==value,'record hash changed')
    manifest=read(record/'manifest.json');require(manifest['server_stopped'] and not manifest.get('execution_error'),'incomplete execution')
    require(manifest['cases_sha256']==lock['cases_sha256'] and manifest['file_sha256']==lock['file_sha256'],'manifest freeze mismatch')
    require([x['case_id'] for x in manifest['attempts']]==list(by_id),'case order changed')
    sources=read(REPO/'experiments/local-generation-smoke/sources.json')
    require(manifest['model_sha256']==sources['model']['expected_sha256'] and manifest['runtime_sha256']==sources['runtime']['server_sha256'],'model pin mismatch')
    review=read(directory/'assistant-review.json');notes={(r['case_id'],r['arm']):r for r in review['rows']}
    require(len(notes)==len(review['rows'])==44 and set(notes)=={(c,a) for c in by_id for a in ARMS},'review coverage mismatch')
    rows=[]
    for entry in manifest['attempts']:
        require(entry['complete'],'partial result');c=by_id[entry['case_id']];result=read(record/entry['result_file'])
        require(sha(record/entry['result_file'])==entry['result_sha256'],'result manifest hash mismatch')
        require(result['case_id']==c['id'] and list(result['arms'])==c['arm_order']==entry['arm_order'],'arm identity/order mismatch')
        calls=0
        for arm in ARMS:
            stage=result['arms'][arm];out=stage['outcome'];plan=plans[c['id']]['plans'][arm];called=out['generator_called']
            require(called==bool(plan['context']),'call/coverage mismatch')
            for key in ('context','ranking','preflight','index_sha256','catalog_sha256'):
                require(out[key]==plan[key],'pipeline plan mismatch: '+key)
            raw=None;value=None;contract_replay='full'
            if called:
                calls+=1;require(stage['request']==expected_request(c['request']['query'],out['context']),'wire request mismatch')
                g=out['generation'];raw=g.get('raw_response')
                if raw is not None:
                    status=int(g['reason'][5:]) if g['status']=='transport_error' and g['reason'].startswith('http_') else 200
                    with patch('http.client.HTTPConnection',return_value=fake_connection(raw,status)):
                        reproduced=run_case(c,arm,BranchedGenerator())
                    require(reproduced==out,'model contract replay mismatch');value=parsed(raw)
                else:
                    require(g['status'] in ('transport_error','invalid_response'),'unexplained missing raw');contract_replay='hash_only_failure_without_raw'
            else:
                spy=Mock();require(run_case(c,arm,spy)==out and stage['request'] is None,'no-run replay mismatch');spy.generate.assert_not_called()
            note=notes[(c['id'],arm)];truth,support,kind=note['truth_correct'],note['cited_support'],note['content_kind']
            require(type(truth) is bool and type(support) is bool and kind in ('factual','refusal','nonanswer','no_output') and note['rationale'],'invalid semantic review')
            ids=value.get('citations',[]) if isinstance(value,dict) else []
            text=value.get('answer') if isinstance(value,dict) else None
            if truth:require(kind=='factual' and isinstance(text,str) and bool(text),'truth annotation without factual answer')
            if support:
                require(kind=='factual' and bool(ids) and c['rubric']['offered_sufficient'] and
                        all(i in c['rubric']['supporting_ids'] for i in ids) and
                        all(i in [h['chunk_id'] for h in out['context']] for i in ids),'support without cited supplied evidence')
            if not called:require(not truth and not support and kind=='no_output','no-run counted as answer')
            accepted=out['status']=='answered';factual=kind=='factual';positive=c['rubric']['offered_sufficient']
            literal=isinstance(text,str) and text in c['rubric']['literal_forms']
            rows.append({'case_id':c['id'],'source_family':c['source_family'],'fact_family':c['fact_family'],
                'release_specific_target':c['release_specific_target'],'condition_id':c['condition_id'],
                'language':c['language'],'arm':arm,'offered_sufficient':positive,
                'packed_support':plans[c['id']]['packed_support'][arm],
                'generator_called':called,'status':out['status'],'reason':out['reason'],
                'raw_answer':text,'citation_ids':ids,'external_gold':c['rubric']['external_gold'],
                'content_kind':kind,'truth_correct':truth,'cited_support':support,'literal_exact':literal,
                'accepted_truth_correct':accepted and factual and truth,
                'accepted_grounded_correct':accepted and factual and truth and support,
                'accepted_grounded_literal_exact':accepted and factual and truth and support and literal,
                'accepted_correct_but_unsupported':accepted and factual and truth and not support,
                'accepted_incorrect_factual':accepted and factual and not truth,
                'accepted_unsupported_factual':accepted and factual and not support,
                'accepted_without_cited_support':accepted and not support,
                'negative_accepted_without_cited_support':not positive and accepted and not support,
                'negative_accepted_unsupported_factual':not positive and accepted and factual and not support,
                'accepted_semantic_nonanswer':accepted and kind in ('refusal','nonanswer'),
                'legitimate_model_refusal':called and not positive and out['status']=='evidence_abstained',
                'false_model_refusal':called and positive and out['status']=='evidence_abstained',
                'deterministic_negative_block':not called and not positive and out['status']=='not_run',
                'invalid_or_transport_failure':out['status'] in ('invalid_response','transport_error'),
                'contract_replay':contract_replay})
        require(calls==entry['generator_calls'],'manifest call count mismatch')
    summaries={a:aggregate([r for r in rows if r['arm']==a]) for a in ARMS}
    groups={field:{name:{a:aggregate([r for r in rows if r['arm']==a and r[field]==name]) for a in ARMS}
                  for name in sorted({r[field] for r in rows})} for field in ('source_family','fact_family','release_specific_target')}
    matched=[]
    for c in cases:
        pair={a:next(r for r in rows if r['case_id']==c['id'] and r['arm']==a) for a in ARMS}
        matched.append({'case_id':c['id'],'positive':c['rubric']['offered_sufficient'],
                        'ungated_grounded':pair['ungated']['accepted_grounded_correct'],
                        'scoped_grounded':pair['scoped']['accepted_grounded_correct'],
                        'unsupported_to_block':pair['ungated']['negative_accepted_without_cited_support'] and pair['scoped']['deterministic_negative_block'],
                        'unsupported_factual_to_block':pair['ungated']['negative_accepted_unsupported_factual'] and pair['scoped']['deterministic_negative_block']})
    joint={a:{target:all(r['accepted_grounded_correct'] for r in rows if r['arm']==a and r['release_specific_target']==target and r['offered_sufficient'])
              for target in sorted({r['release_specific_target'] for r in rows})} for a in ARMS}
    return {'record_integrity':'verified','semantic_review':'AI annotations of release truth and actual cited supplied support; not automatic entailment or human calibration',
            'denominators':{'source_families':2,'setting_fact_families':3,'release_specific_targets':5,'conditions':11,'rows_per_arm':22,'positive_rows_per_arm':10,'negative_rows_per_arm':12},
            'summary':summaries,'groups':groups,'both_languages_positive_target_success':joint,'matched':matched,'rows':rows}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--check',action='store_true');args=parser.parse_args();value=audit()
    if args.check:
        require(value==read(HERE/'summary.json'),'summary mismatch');print('Two-source raw/contract/coverage/truth-support summary matches offline replay.')
    else:print(canonical_json(value),end='')
