"""Checks for exact citations, actual near-misses and backward compatibility."""

import json
from pathlib import Path
import subprocess
import sys
import unittest

from replay import CASES, T17_QUERY, replay

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


class TransferReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = replay()
        cls.rows = {row["case"]: row for row in cls.report["rows"]}

    def test_exact_cli_locator_field_value_and_unit(self):
        for key, fragment in (("pg17-transaction", "#L9368-L9382"),
                              ("pg17-statement", "#L9332-L9346")):
            with self.subTest(key=key):
                result = subprocess.run([sys.executable, "-B", str(HERE / "replay.py"), "--case", key],
                                        cwd=ROOT, capture_output=True, text=True, timeout=10, check=True)
                value = json.loads(result.stdout)["result"]
                self.assertIs(type(value["answer"]["value"]), int)
                self.assertEqual(value["answer"], {"value": 0, "value_type": "integer", "unit": "milliseconds"})
                citation, = value["citations"]
                self.assertEqual(citation["source"].count("#"), 1)
                self.assertTrue(citation["source"].endswith(fragment))

    def test_all_decoys_hit_without_scope_but_fail_before_actual_ranking(self):
        for name in ("pg17-neighbors-only", "pg16-neighbors-only", "pg17-exception-only"):
            with self.subTest(name=name):
                r = self.rows[name]
                self.assertTrue(r["unscoped_diagnostic_hits"])
                self.assertEqual(r["result"]["reason"], "no_matching_scope")
                self.assertEqual(r["result"]["ranking_attempts"], 0)
                self.assertEqual(r["result"]["trace"][1]["matched_ids"], [])
                self.assertEqual(r["result"]["citations"], [])

    def test_same_intent_used_when_relevant_evidence_removed(self):
        for name in ("pg17-transaction", "pg17-neighbors-only", "pg17-exception-only"):
            self.assertEqual(CASES[name][0], T17_QUERY)
        self.assertEqual(self.report["supported_positive_plans"], 2)
        self.assertEqual(self.report["accepted_negative_plans"], 0)
        self.assertEqual(self.report["agent_retrieval_attempts"], 5)
        self.assertEqual(self.report["agent_ranking_attempts"], 2)
        self.assertEqual(self.report["separate_unscoped_diagnostic_passes"], 3)
        self.assertEqual(self.report["model_calls"], 0)

    def test_original_cli_acceptance_remains_byte_identical(self):
        subprocess.run([sys.executable, "-B", str(ROOT / "experiments/read-only-agent-v1/replay.py"), "--check"],
                       cwd=ROOT, capture_output=True, timeout=20, check=True)
