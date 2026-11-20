"""Input/lexical invariants before live calls; no hidden oracle text or model."""
import copy
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parent))
from adapter import run_case,make_pipeline,expected_request
from build_fixture import build
from preflight import preflight
from rag_foundation.scoped_pipeline import ReviewedValue
from rag_foundation.corpus import Chunk

HERE=Path(__file__).resolve().parent


class FixtureTests(unittest.TestCase):
    def setUp(self):self.fixture=build();self.cases=self.fixture['cases']

    def test_frozen_builder_and_coverage_reproduce(self):
        self.assertEqual(self.fixture,json.loads((HERE/'cases.json').read_text()))
        self.assertEqual(preflight(),json.loads((HERE/'preflight.json').read_text()))

    def test_denominators_and_no_hidden_zero_overlap(self):
        p=preflight();self.assertEqual(len(self.cases),22);self.assertEqual(p['expected_model_calls'],32)
        self.assertEqual(sum(c['rubric']['offered_sufficient'] for c in self.cases),10)
        self.assertEqual(len({c['fact_family'] for c in self.cases}),3)
        self.assertEqual(len({c['release_specific_target'] for c in self.cases}),5)
        self.assertTrue(all(r['plans']['ungated']['context'] for r in p['rows']))
        self.assertEqual(sum(r['packed_support']['ungated'] for r in p['rows']),9)
        self.assertEqual(sum(r['packed_support']['scoped'] for r in p['rows']),10)

    def test_wrong_version_evidence_actually_packed(self):
        for c in self.cases:
            if 'older-only' in c['id']:
                result=run_case(c,'ungated')
                expected='p13presence' if c['id'].startswith('py-') else 'e4default'
                self.assertEqual([h['chunk_id'] for h in result['context']],[expected])
                self.assertEqual(run_case(c,'scoped')['reason'],'no_matching_scope')

    def test_explicit_is_distinct_production_scope_not_description_only(self):
        for c in self.cases:
            if 'explicit-only' in c['id']:
                idx=make_pipeline(c).index
                self.assertTrue(all(s.key.endswith('.explicit_example') for s in idx.scopes.values()))
                self.assertTrue(c['request']['scope']['key'].endswith('.default'))
                self.assertEqual(run_case(c,'scoped')['preflight']['matched_count'],0)

    def test_boolean_strings_not_native_bool_zero_or_missing(self):
        for c in self.cases:
            idx=make_pipeline(c).index
            for value in idx.claims.values():
                self.assertEqual(value.value_type,'string');self.assertIs(type(value.value),str)
        c=self.cases[0];entry=copy.deepcopy(c['catalog']['entries'][0]['claim']);chunk=Chunk(**c['chunks'][0])
        for wrong in (False,0,None):
            entry['value']=wrong
            with self.subTest(wrong=wrong),self.assertRaises(ValueError):ReviewedValue.bind(entry,chunk)
        absent=next(c for c in self.cases if c['id']=='py-absence-supported-en')
        self.assertEqual(absent['rubric']['external_gold'],'absent')
        self.assertNotIn('False',absent['rubric']['literal_forms'])

    def test_rubric_and_source_oracle_not_sent(self):
        for c in self.cases:
            r=run_case(c,'ungated');payload=expected_request(c['request']['query'],r['context'])
            actual=json.loads(payload['messages'][1]['content'])
            self.assertEqual(set(actual),{'query','source_excerpts'})
            self.assertTrue(all(set(s)=={'chunk_id','text'} for s in actual['source_excerpts']))
            changed=copy.deepcopy(c);changed['rubric']['external_gold']='NOT A VALUE';changed['source_refs']={}
            self.assertEqual(run_case(c,'ungated'),run_case(changed,'ungated'))

    def test_matched_queries_and_counterbalanced_arm_order(self):
        groups={}
        for c in self.cases:groups.setdefault((c['release_specific_target'],c['language']),set()).add(c['request']['query'])
        self.assertTrue(all(len(v)==1 for v in groups.values()))
        for cid in {c['condition_id'] for c in self.cases}:
            pair=[c for c in self.cases if c['condition_id']==cid]
            self.assertEqual(pair[0]['arm_order'],list(reversed(pair[1]['arm_order'])))

    def test_no_full_oracle_source_text_in_fixture(self):
        # Publication holds only provenance receipts plus original short summaries.
        self.assertTrue(all(len(c['text'])<300 for row in self.cases for c in row['chunks']))
        self.assertTrue(all(c['source_url'].startswith('authored-summary://') for row in self.cases for c in row['chunks']))
        manifest=json.loads((HERE/'source-manifest.json').read_text());self.assertEqual(len(manifest),12)
        self.assertTrue(all(row['url'].startswith('https://raw.githubusercontent.com/') for row in manifest))


if __name__=='__main__':unittest.main()
