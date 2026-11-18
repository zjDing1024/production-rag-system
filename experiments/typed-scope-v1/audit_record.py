"""Offline provenance/contract replay with disclosed AI semantic annotations."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from unittest.mock import Mock, patch
from adapter import BranchedGenerator, parse_input, plan, answer, expected_request
from build_fixture import build
from rag_foundation.generation import strict_json

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
ARMS=('ungated','gated')


def read(p):return strict_json(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def require(ok,msg):
    if not ok:raise ValueError(msg)


def connection(raw,status):
    conn,response=Mock(),Mock();response.status=status;response.read.return_value=raw.encode('utf-8');conn.getresponse.return_value=response
    return conn


def parsed(raw):
    try:return strict_json(strict_json(raw)['choices'][0]['message']['content'])
    except (TypeError,ValueError,KeyError,IndexError):return None


def audit(directory=HERE):
    fixture,lock=read(directory/'cases.json'),read(directory/'cases.lock.json')
    require(lock['status']=='frozen_before_execution' and sha(directory/'cases.json')==lock['cases_sha256'],'fixture hash changed')
    require(fixture==build(),'fixture rebuild mismatch')
    for name,value in lock['file_sha256'].items():require(sha(REPO/name)==value,'frozen file changed: '+name)
    for source in read(directory/'sources/manifest.json'):
        if 'local_source' in source:
            path=REPO/source['local_source'];text=path.read_text()
            require(sha(path)==source['source_sha256'],'local upstream source changed')
            require(hashlib.sha256(text[source['char_start']:source['char_end']].encode()).hexdigest()==source['excerpt_sha256'],'local source excerpt changed')
    cases={c['id']:c for c in fixture['cases']};require(len(cases)==64,'wrong case set')
    planned=[]
    for c in cases.values():
        q,s,r=parse_input(c['input']);p=plan(q,s,r,True)
        require(p['gate']['matched_ids']==c['supporting_ids'],'frozen metadata label mismatch')
        planned.append({'case_id':c['id'],'matched_ids':p['gate']['matched_ids'],'planned_status':p['status'],
                        'gated_expected_call':bool(p['context']),'ungated_expected_call':True})
    require(read(directory/'preflight.json')['rows']==planned,'preflight mismatch')
    record=directory/'recorded';index=read(directory/'recorded-files.sha256.json')
    require(set(index)=={p.name for p in record.glob('*.json')},'archive file list changed')
    for name,value in index.items():require(Path(name).name==name and sha(record/name)==value,'record hash changed: '+name)
    manifest=read(record/'manifest.json')
    require(manifest['server_stopped'] and not manifest.get('execution_error'),'execution incomplete')
    require(manifest['cases_sha256']==lock['cases_sha256'] and manifest['file_sha256']==lock['file_sha256'],'manifest freeze mismatch')
    require([e['case_id'] for e in manifest['attempts']]==list(cases),'case order mismatch')
    pins=read(REPO/'experiments/local-generation-smoke/sources.json')
    require(manifest['model_sha256']==pins['model']['expected_sha256'] and manifest['runtime_sha256']==pins['runtime']['server_sha256'],'asset pin mismatch')
    review=read(directory/'assistant-review.json');reviews={(r['case_id'],r['arm']):r for r in review['rows']}
    require(len(reviews)==len(review['rows'])==128 and set(reviews)=={(c,a) for c in cases for a in ARMS},'review set mismatch')
    rows=[]
    for entry in manifest['attempts']:
        c=cases[entry['case_id']];require(entry['complete'],'partial row')
        require(sha(record/entry['result_file'])==entry['result_sha256'],'manifest result hash mismatch')
        result=read(record/entry['result_file']);require(result['case_id']==c['id'],'identity mismatch')
        require(list(result['arms'])==entry['arm_order']==c['arm_order'],'arm order mismatch')
        q,s,r=parse_input(c['input']);calls=0
        for arm in ARMS:
            stage=result['arms'][arm];out=stage['outcome'];call=out['generator_called'];raw=None;value=None
            initial=plan(q,s,r,arm=='gated')
            require(call==bool(initial['context']),'routing mismatch')
            for key in ('context','gate','requested_scope','supplied_ids','gate_enabled','semantic_support'):
                require(out[key]==initial[key],'scope plan mismatch: '+key)
            replay_status='full_contract_replay'
            if call:
                calls+=1;require(stage['request']==expected_request(q,out['context']),'wire request mismatch')
                g=out['generation'];raw=g.get('raw_response')
                if raw is not None:
                    http_status=int(g['reason'][5:]) if g['status']=='transport_error' and g['reason'].startswith('http_') else 200
                    with patch('http.client.HTTPConnection',return_value=connection(raw,http_status)):
                        replay=answer(q,s,r,BranchedGenerator(),arm=='gated')
                    require(replay==out,'generation contract replay mismatch')
                    value=parsed(raw)
                else:
                    require(g['status'] in ('transport_error','invalid_response'),'unexplained missing raw output')
                    replay_status='failure_record_hash_only_no_raw_payload'
            else:
                dummy=Mock();replay=answer(q,s,r,dummy,arm=='gated');require(replay==out,'no-run replay mismatch');dummy.generate.assert_not_called()
                require(stage['request'] is None,'request saved despite no-run')
            note=reviews[(c['id'],arm)];correct=note['answer_value_correct'];require(type(correct) is bool and note['rationale'],'invalid semantic annotation')
            ids=value.get('citations',[]) if isinstance(value,dict) else []
            ids=ids if isinstance(ids,list) else []
            any_scope=any(i in c['supporting_ids'] for i in ids)
            all_scope=bool(ids) and all(i in c['supporting_ids'] for i in ids)
            accepted=out['status']=='answered'
            strict_correct=accepted and correct and all_scope
            model_refusal=call and out['status']=='evidence_abstained'
            no_run=not call and out['status']=='not_run'
            correct_block=no_run and not c['offered_sufficient']
            legitimate_refusal=model_refusal and not c['offered_sufficient']
            if correct:require(c['offered_sufficient'] and isinstance(value,dict) and bool(value.get('answer')),'impossible value-correct annotation')
            rows.append({'case_id':c['id'],'group':c['group'],'fact_family':c['fact_family'],'pair_id':c['pair_id'],
                'language':c['language'],'layout':c['layout'],'condition':c['condition'],'arm':arm,
                'offered_sufficient':c['offered_sufficient'],'generator_called':call,'status':out['status'],
                'raw_answer':value.get('answer') if isinstance(value,dict) else None,'citation_ids':ids,
                'cited_source_identities':[c['source_identities'].get(i,'unknown') for i in ids],
                'any_scoped_citation':any_scope,'all_citations_scoped':all_scope,'answer_value_correct':correct,
                'accepted_supported_correct':strict_correct,
                'accepted_supported_literal_exact':accepted and all_scope and c['offered_sufficient'] and isinstance(value,dict) and value.get('answer')==str(c['expected_value']),
                'accepted_without_scoped_citation':accepted and not any_scope,
                'accepted_mixed_scope_citations':accepted and any_scope and not all_scope,
                'accepted_wrong_value_with_scoped_citations':accepted and all_scope and not correct,
                'model_refusal':model_refusal,'legitimate_model_refusal':legitimate_refusal,
                'correct_metadata_block':correct_block,'false_metadata_block':no_run and c['offered_sufficient'],
                'final_success':strict_correct if c['offered_sufficient'] else (correct_block or legitimate_refusal),
                'replay':replay_status})
        require(calls==entry['generator_calls'],'manifest callback mismatch')
    pair_ids=sorted({c['pair_id'] for c in cases.values()});pairs=[]
    for pid in pair_ids:
        c=next(c for c in cases.values() if c['pair_id']==pid)
        pairs.append({'pair_id':pid,'group':c['group'],'language':c['language'],'layout':c['layout'],
                      'success':{a:all(r['final_success'] for r in rows if r['pair_id']==pid and r['arm']==a) for a in ARMS}})
    summaries={}
    for arm in ARMS:
        rr=[r for r in rows if r['arm']==arm]
        summaries[arm]={'offered_rows':64,'sufficient_rows':32,'insufficient_rows':32,
            'model_calls':sum(r['generator_called'] for r in rr),'status_counts':dict(sorted(Counter(r['status'] for r in rr).items())),
            **{key:sum(r[key] for r in rr) for key in ('accepted_supported_correct','accepted_supported_literal_exact','accepted_without_scoped_citation',
                'accepted_mixed_scope_citations','accepted_wrong_value_with_scoped_citations','legitimate_model_refusal',
                'correct_metadata_block','false_metadata_block','final_success')},
            'complete_pairs':sum(p['success'][arm] for p in pairs),
            'both_languages_group_layout_success':sum(all(p['success'][arm] for p in pairs if p['group']==g and p['layout']==l)
                for g in ('v_old','v_new','entity','time') for l in ('o0i0','o0i1','o1i0','o1i1')),
            'all_layouts_both_languages_request_groups':sum(all(p['success'][arm] for p in pairs if p['group']==g)
                for g in ('v_old','v_new','entity','time')),
            'by_group':{g:{'sufficient_rows':8,'accepted_supported_correct':sum(r['accepted_supported_correct'] for r in rr if r['group']==g),
                'accepted_supported_literal_exact':sum(r['accepted_supported_literal_exact'] for r in rr if r['group']==g),
                'correct_metadata_block':sum(r['correct_metadata_block'] for r in rr if r['group']==g)}
                for g in ('v_old','v_new','entity','time')},
            'version_switch_positive_pairs':sum(all(r['accepted_supported_correct'] for r in rr if r['group'] in ('v_old','v_new')
                 and r['language']==lang and r['layout']==layout and r['offered_sufficient'])
                 for lang in ('en','zh') for layout in ('o0i0','o0i1','o1i0','o1i1'))}
    return {'record_integrity':'verified','semantic_review':'AI annotations; metadata/source identity checks are not general entailment or query understanding',
            'new_upstream_bytes':'not fetched by offline audit; pinned verification receipt retained',
            'summary':summaries,'pairs':pairs,'rows':rows}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--check',action='store_true');args=parser.parse_args();value=audit()
    if args.check:
        require(value==read(HERE/'summary.json'),'summary mismatch');print('Recorded typed-scope summary matches offline replay.')
    else:print(json.dumps(value,ensure_ascii=False,indent=2))
