"""Deterministic mechanism/transport contracts, not model-quality tests."""
from dataclasses import asdict, replace
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import copy
import json
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import Mock

from rag_foundation.corpus import Chunk, digest, write_chunks
from rag_foundation.generation import LocalGenerator
from rag_foundation.retrieval import BM25
from rag_foundation.scope_gate import Scope
from rag_foundation.scoped_pipeline import ClaimIndex, EligibleBM25, ScopedGenerationPipeline, chunks_fingerprint

ROOT = Path(__file__).resolve().parents[1]
SCOPE = Scope('runtime','Cedar','wait',observed_at='2032-07-08T09:00:00Z')


def chunk(cid, text):
    return Chunk(cid,cid,'Original fixture',text,'synthetic://test/'+cid,digest(text.encode()),'MIT',0,len(text),1,1)


def catalog(chunks, values=None, scopes=None):
    values = values or [30]*len(chunks)
    scopes = scopes or [SCOPE]*len(chunks)
    return {'schema_version':1,'complete':True,'chunks_sha256':chunks_fingerprint(chunks),
            'entries':[{'chunk_id':c.id,'scope':asdict(s),'claim':{
                'reviewed':True,'chunk_text_sha256':digest(c.text.encode()),'value_type':'integer','unit':'seconds',
                'value':v,'start_char':0,'end_char':len(c.text),'quote':c.text}}
                       for c,v,s in zip(chunks,values,scopes)]}


def spy(status='answered'):
    x=Mock();x.generate.return_value={'status':status,'reason':'fixture','citation_ids':[], 'answer':None,'raw_response':None};return x


class IndexedScopeTests(unittest.TestCase):
    def setUp(self):
        self.chunks=[chunk('hot','cache timeout: 30 seconds'),chunk('cold','The duration is ninety seconds.')]

    def make(self, values=(30,90)):
        return ClaimIndex(self.chunks,catalog(self.chunks,values))

    def test_hidden_conflict_before_any_ranking_or_generation(self):
        idx=self.make();self.assertEqual([h.chunk.id for h in idx.bm25.search('cache timeout',2)],['hot'])
        idx.bm25.search=Mock(side_effect=AssertionError('ranking must not happen'))
        g=spy();result=ScopedGenerationPipeline(idx,g).answer('cache timeout',SCOPE,k=1,scope_gate=True)
        self.assertEqual(result['reason'],'reviewed_value_conflict');self.assertEqual(result['preflight']['reviewed_count'],2)
        self.assertIsNone(result['ranking']);g.generate.assert_not_called()

    def test_lexical_zero_agreement_can_proceed(self):
        g=spy();result=ScopedGenerationPipeline(self.make((30,30)),g).answer('cache timeout',SCOPE,k=1,scope_gate=True)
        self.assertTrue(result['generator_called']);self.assertEqual(result['ranking']['zero_overlap_count'],1)
        self.assertEqual([c['chunk_id'] for c in result['context']],['hot'])

    def test_scope_check_default_off(self):
        g=spy();result=ScopedGenerationPipeline(self.make(),g).answer('cache timeout',SCOPE,k=1)
        self.assertTrue(result['generator_called']);self.assertIsNone(result['preflight'])

    def test_full_corpus_scores_exact_and_not_subset_recomputed(self):
        chunks=self.chunks+[chunk('noise','cache cache cache cache')];full=BM25(chunks);idx=EligibleBM25(chunks)
        before={h.chunk.id:h.score for h in full.search('cache timeout',3)}
        filtered=idx.search('cache timeout',1,eligible_ids={'hot'})
        self.assertEqual(filtered[0].score,before['hot'])
        self.assertNotEqual(filtered[0].score,BM25([chunks[0]]).search('cache timeout',1)[0].score)
        self.assertEqual(idx.lengths,full.lengths);self.assertEqual(idx.postings,full.postings)
        self.assertEqual(idx.avg_length,full.avg_length)

    def test_eligibility_before_topk(self):
        chunks=[chunk('wrong','cache timeout'),chunk('good','cache timeout '+'neutral '*30)]
        idx=EligibleBM25(chunks)
        self.assertEqual(idx.search('cache timeout',1)[0].chunk.id,'wrong')
        self.assertEqual(idx.search('cache timeout',1,eligible_ids={'good'})[0].chunk.id,'good')

    def test_eligible_validation(self):
        idx=EligibleBM25(self.chunks)
        for ids in (['hot'],{'absent'},{1}):
            with self.subTest(ids=ids),self.assertRaises(ValueError):idx.search('cache',1,eligible_ids=ids)
        self.assertEqual(idx.search('cache',1,eligible_ids=set()),[])

    def test_wrong_scope_conflict_ignored(self):
        other=replace(SCOPE,subject='Birch');idx=ClaimIndex(self.chunks,catalog(self.chunks,[30,90],[SCOPE,other]))
        self.assertEqual(idx.assess(SCOPE)['status'],'consistent')

    def test_exact_time_and_version(self):
        idx=self.make((30,30));self.assertEqual(idx.assess(replace(SCOPE,observed_at='2032-07-08T08:00:00Z'))['status'],'no_match')
        old=Scope('documentation','Flask','key',version='1.1.4');new=replace(old,version='3.1.2')
        idx=ClaimIndex(self.chunks,catalog(self.chunks,[30,90],[old,new]));self.assertEqual(idx.assess(old)['matched_ids'],['hot'])

    def test_missing_scope_is_global_unknown_not_ignored(self):
        cat=catalog(self.chunks);cat['entries'][1]['scope']=None
        idx=ClaimIndex(self.chunks,cat);self.assertEqual(idx.assess(SCOPE)['reason'],'catalog_incomplete')
        self.assertEqual(idx.assess(replace(SCOPE,subject='nobody'))['reason'],'catalog_incomplete')

    def test_missing_entry_and_declared_incomplete(self):
        for change in ('entry','complete'):
            cat=catalog(self.chunks)
            if change=='entry':cat['entries'].pop()
            else:cat['complete']=False
            self.assertEqual(ClaimIndex(self.chunks,cat).assess(SCOPE)['reason'],'catalog_incomplete')

    def test_missing_review_not_literal_null(self):
        cat=catalog(self.chunks);cat['entries'][1]['claim']=None
        result=ClaimIndex(self.chunks,cat).assess(SCOPE)
        self.assertEqual(result['reason'],'missing_reviewed_claim');self.assertEqual(result['reviewed_count'],1)
        one=[self.chunks[0]];cat=catalog(one);cat['entries'][0]['claim'].update(value_type='null',value=None,unit='configuration')
        self.assertEqual(ClaimIndex(one,cat).assess(SCOPE)['status'],'consistent')

    def test_incomparable_types_and_units_are_unknown(self):
        for update in ({'unit':'minutes'},{'value_type':'null','value':None}):
            cat=catalog(self.chunks);cat['entries'][1]['claim'].update(update)
            self.assertEqual(ClaimIndex(self.chunks,cat).assess(SCOPE)['reason'],'incomparable_claims')

    def test_scan_cap_before_ranking(self):
        idx=self.make((30,30));g=spy();result=ScopedGenerationPipeline(idx,g).answer('cache',SCOPE,scope_gate=True,scan_limit=1)
        self.assertEqual(result['reason'],'scope_scan_limit');self.assertFalse(result['preflight']['scope_scan_complete']);self.assertIsNone(result['ranking']);g.generate.assert_not_called()

    def test_budget_no_match_lexical_distinct(self):
        idx=self.make((30,30));g=spy();pipeline=ScopedGenerationPipeline(idx,g)
        self.assertEqual(pipeline.answer('cache',SCOPE,scope_gate=True,context_characters=1)['reason'],'context_budget_exhausted')
        self.assertEqual(pipeline.answer('cache',replace(SCOPE,subject='nobody'),scope_gate=True)['reason'],'no_matching_scope')
        self.assertEqual(pipeline.answer('absentword',SCOPE,scope_gate=True)['reason'],'no_lexical_candidates');g.generate.assert_not_called()

    def test_conflict_not_hidden_by_tiny_context_budget(self):
        result=ScopedGenerationPipeline(self.make(),spy()).answer('cache',SCOPE,k=1,context_characters=1,scope_gate=True)
        self.assertEqual(result['reason'],'reviewed_value_conflict')

    def test_partial_packing_after_complete_review(self):
        chunks=[chunk('a','cache 30'),chunk('b','cache 30')];idx=ClaimIndex(chunks,catalog(chunks));g=spy()
        r=ScopedGenerationPipeline(idx,g).answer('cache',SCOPE,k=2,context_characters=8,scope_gate=True)
        self.assertEqual(r['preflight']['reviewed_count'],2);self.assertEqual(r['ranking']['budget_omitted_ids'],['b']);self.assertTrue(r['generator_called'])

    def test_hash_and_span_binding_reject_changes(self):
        cat=catalog(self.chunks)
        with self.assertRaisesRegex(ValueError,'fingerprint'):ClaimIndex([replace(self.chunks[0],text='other'),self.chunks[1]],cat)
        for update in ({'chunk_text_sha256':'bad'},{'quote':'not the source'},{'end_char':9999}):
            changed=copy.deepcopy(cat);changed['entries'][0]['claim'].update(update)
            with self.subTest(update=update),self.assertRaises(ValueError):ClaimIndex(self.chunks,changed)

    def test_catalog_is_construction_snapshot_not_external_mutable_dict(self):
        cat=catalog(self.chunks);idx=ClaimIndex(self.chunks,cat);cat['entries'][0]['claim']['value']=999
        self.assertEqual(idx.claims['hot'].value,30)
        with self.assertRaises(TypeError):idx.scopes['hot']=None

    def test_value_semantics_not_proven_by_hash(self):
        cat=catalog(self.chunks,[999,999]);idx=ClaimIndex(self.chunks,cat)
        self.assertEqual(idx.assess(SCOPE)['status'],'consistent')
        self.assertEqual(idx.assess(SCOPE)['semantic_support'],'unverified')

    def test_query_scope_agreement_not_inferred(self):
        idx=self.make((30,30));r=ScopedGenerationPipeline(idx).answer('cache timeout for wrong application',SCOPE,scope_gate=True)
        self.assertEqual(r['status'],'planned');self.assertEqual(r['semantic_support'],'unverified')

    def test_invalid_claim_types(self):
        for update in ({'value':True},{'value':1.0},{'value_type':'array','value':[30]},{'reviewed':False},{'unit':''}):
            cat=catalog(self.chunks);cat['entries'][0]['claim'].update(update)
            with self.subTest(update=update),self.assertRaises(ValueError):ClaimIndex(self.chunks,cat)

    def test_invalid_catalog_and_duplicate_ids(self):
        cat=catalog(self.chunks)
        for c in (dict(cat,extra=1),dict(cat,complete=1),dict(cat,schema_version=True)):
            with self.assertRaises(ValueError):ClaimIndex(self.chunks,c)
        cat['entries'][1]=copy.deepcopy(cat['entries'][0])
        with self.assertRaises(ValueError):ClaimIndex(self.chunks,cat)

    def test_bounds_and_no_generator_plan(self):
        p=ScopedGenerationPipeline(self.make((30,30)))
        self.assertEqual(p.answer('cache',SCOPE,scope_gate=True)['status'],'planned')
        for opts in ({'k':0},{'k':True},{'context_characters':0},{'scan_limit':2049},{'scope_gate':1}):
            with self.subTest(opts=opts),self.assertRaises(ValueError):p.answer('cache',SCOPE,**opts)

    def test_generator_outcomes_preserved(self):
        for status in ('answered','evidence_abstained','invalid_response','transport_error'):
            g=spy(status);r=ScopedGenerationPipeline(self.make((30,30)),g).answer('cache',SCOPE,scope_gate=True)
            self.assertEqual(r['status'],status);self.assertEqual(r['generation'],g.generate.return_value)

    def test_actual_local_http_contract_and_allowed_context(self):
        captured=[]
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                captured.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
                content=json.dumps({'answer':'TRANSPORT FIXTURE, NOT MODEL INFERENCE','citations':['hot'],'abstain':False})
                body=json.dumps({'choices':[{'finish_reason':'stop','message':{'content':content}}]}).encode()
                self.send_response(200);self.end_headers();self.wfile.write(body)
            def log_message(self,*args):pass
        server=HTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            gen=LocalGenerator('http://127.0.0.1:'+str(server.server_port),timeout=2)
            r=ScopedGenerationPipeline(self.make((30,30)),gen).answer('cache timeout',SCOPE,k=1,scope_gate=True)
            self.assertEqual(r['status'],'answered');self.assertEqual(r['generation']['citation_ids'],['hot'])
            payload=json.loads(captured[0]['messages'][1]['content']);self.assertEqual([c['chunk_id'] for c in payload['source_excerpts']],['hot'])
        finally:server.shutdown();thread.join(timeout=2);server.server_close()

    def test_cli_and_request_cannot_supply_records(self):
        with tempfile.TemporaryDirectory() as directory:
            d=Path(directory);write_chunks(self.chunks,d/'chunks.jsonl');(d/'catalog.json').write_text(json.dumps(catalog(self.chunks,[30,30])))
            req={'query':'cache timeout','scope':asdict(SCOPE)};(d/'request.json').write_text(json.dumps(req))
            command=[sys.executable,'-m','rag_foundation.scoped_pipeline','--chunks',str(d/'chunks.jsonl'),'--catalog',str(d/'catalog.json'),'--request',str(d/'request.json'),'--scope-gate','-k','1']
            result=subprocess.run(command,capture_output=True,text=True);self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(json.loads(result.stdout)['status'],'planned')
            req['records']=[];(d/'request.json').write_text(json.dumps(req));self.assertNotEqual(subprocess.run(command,capture_output=True).returncode,0)


if __name__=='__main__':unittest.main()
