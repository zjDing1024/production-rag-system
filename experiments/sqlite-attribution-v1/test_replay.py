"""Fixture acceptance, actual lexical hits, and runtime oracle separation."""

import unittest
from unittest.mock import patch

from fixture import FIXTURE_ID, QUESTION, TARGET, WRONG_FIELD, runtime_oracle
from replay import ALL_EVIDENCE, pipeline_for, replay, run_bound, scope


class SQLiteReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.record = replay()

    def test_crossed_citations_use_expected_wrong_identity_and_rank(self):
        rows = {r["case"]: r for r in self.record["rows"]}
        for name, chosen in (("wrong_object_same_value", "temp-hidden"),
                             ("wrong_field_same_value", "main-cid")):
            with self.subTest(name=name):
                r = rows[name]
                self.assertIn("main-hidden", r["catalog_ids"])
                self.assertEqual(r["version_check"], "literal_release_matches")
                self.assertGreater(r["baseline"]["scope_lexical_hits"], 0)
                self.assertEqual(r["baseline"]["packed_ids"], [chosen])
                self.assertIs(r["baseline"]["numeric_exact_match"], True)
                self.assertIs(r["baseline"]["citation_support"], False)
                self.assertEqual(r["fixture_bound"]["reason"], "fixture_scope_mismatch")
                self.assertFalse(r["fixture_bound"]["ranking_performed"])
                self.assertIsNone(r["fixture_bound"]["numeric_exact_match"])

    def test_positive_and_missing_evidence_not_conflated(self):
        pos, *_, missing = self.record["rows"]
        for arm in ("baseline", "fixture_bound"):
            self.assertEqual(pos[arm]["packed_ids"], ["main-hidden"])
            self.assertIs(pos[arm]["citation_support"], True)
            self.assertEqual(missing[arm]["reason"], "no_matching_scope")
            self.assertEqual(missing[arm]["packed_ids"], [])
            self.assertFalse(missing[arm]["ranking_performed"])
            self.assertIsNone(missing[arm]["citation_support"])

    def test_scope_rejections_precede_pipeline(self):
        p = pipeline_for(ALL_EVIDENCE)
        with patch.object(p, "answer", side_effect=AssertionError("must not run")) as answer:
            r = run_bound(p, FIXTURE_ID, QUESTION, scope(WRONG_FIELD))
            self.assertEqual(r["reason"], "fixture_scope_mismatch")
            for fixture_id, question in ((FIXTURE_ID, QUESTION + " "), ("unknown", QUESTION)):
                self.assertEqual(run_bound(p, fixture_id, question, scope(TARGET))["reason"],
                                 "unknown_fixture_request")
            answer.assert_not_called()

    def test_result_counts(self):
        for arm, unsupported, blocks in (("baseline", 2, 0), ("fixture_bound", 0, 2)):
            self.assertEqual(self.record["metrics"][arm], {
                "correct_with_support": 1, "fixture_blocks": blocks, "generator_calls": 0,
                "missing_scope_stops": 1, "numeric_match_without_support": unsupported,
            })

    def test_actual_in_memory_runtime(self):
        result = runtime_oracle()
        self.assertTrue(result["source_id"])
        rows = result["rows"]
        for key, hidden in (("main_xinfo", 3), ("temp_xinfo", 3), ("virtual_xinfo", 2)):
            last = rows[key][-1]
            self.assertEqual(last, {"cid": 3, "name": "derived", "hidden": hidden})
            self.assertIs(type(last["cid"]), int)
            self.assertIs(type(last["hidden"]), int)
        self.assertEqual([r["name"] for r in rows["main_info"]], ["raw", "aux1", "aux2"])
