import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parent))
from adapter import parse_input, plan, expected_request
from build_fixture import build


class FixtureTests(unittest.TestCase):
    def setUp(self):
        self.cases = build()['cases']

    def test_frozen_file_rebuilds(self):
        self.assertEqual(build(), json.loads((Path(__file__).parent/'cases.json').read_text()))

    def test_scope_matching_all_rows_has_no_answer_field(self):
        for case in self.cases:
            query, scope, records = parse_input(case['input'])
            result = plan(query, scope, records, True)
            self.assertEqual(result['gate']['matched_ids'], case['supporting_ids'])
            self.assertEqual(bool(result['context']), case['offered_sufficient'])
            self.assertNotIn('value', vars(scope))

    def test_same_question_pair_same_kind_count_and_lengths(self):
        for pair in {c['pair_id'] for c in self.cases}:
            a,b=[c for c in self.cases if c['pair_id']==pair]
            self.assertEqual(a['input']['query'],b['input']['query'])
            self.assertEqual(a['input']['scope'],b['input']['scope'])
            self.assertNotEqual(a['offered_sufficient'],b['offered_sufficient'])
            self.assertEqual([len(r['text']) for r in a['input']['records']], [len(r['text']) for r in b['input']['records']])
            for c in (a,b):
                self.assertEqual(len(c['input']['records']),2)
                self.assertEqual(len({r['scope']['kind'] for r in c['input']['records']}),1)

    def test_independent_order_and_id_factorial(self):
        positives=[c for c in self.cases if c['offered_sufficient']]
        for group in {c['group'] for c in positives}:
            for lang in ('en','zh'):
                rows=[c for c in positives if c['group']==group and c['language']==lang]
                combos={(next(i for i,r in enumerate(c['input']['records']) if r['record_id'] in c['supporting_ids']), c['supporting_ids'][0]) for c in rows}
                self.assertEqual(combos,{(0,'q7'),(1,'q7'),(0,'m2'),(1,'m2')})

    def test_both_arms_same_generator_contract(self):
        case=next(c for c in self.cases if c['offered_sufficient'])
        q,s,r=parse_input(case['input'])
        a=expected_request(q,plan(q,s,r,False)['context'])
        b=expected_request(q,plan(q,s,r,True)['context'])
        self.assertEqual(a['messages'][0],b['messages'][0])
        for key in ('model','temperature','seed','max_tokens','stream','chat_template_kwargs'):
            self.assertEqual(a[key],b[key])
        self.assertIn('anyOf',a['response_format']['json_schema']['schema'])
        self.assertIn('anyOf',b['response_format']['json_schema']['schema'])

    def test_gate_no_run_count_fixed(self):
        self.assertEqual(len(self.cases),64)
        self.assertEqual(sum(c['offered_sufficient'] for c in self.cases),32)
        self.assertEqual(len({c['pair_id'] for c in self.cases}),32)


if __name__=='__main__':unittest.main()
