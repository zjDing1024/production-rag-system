import json
from pathlib import Path
import subprocess
import sys
import unittest

from audit import HERE, ROOT, grade_answer, load_fixture, plan_case
from live import check, verify_lock


class CPythonProvenanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = load_fixture()
        cls.cases = {case["id"]: case for case in cls.fixture["cases"]}

    def test_exact_integer_unit_id_and_source_are_jointly_required(self):
        case = self.cases["py311-connection-shutdown"]
        citation = case["expected_citation"]
        locator = citation["source_url"]
        actual = [{**citation, "locator": locator}]
        self.assertTrue(grade_answer(case, "30 seconds", actual)["verified_exact"])
        for invalid in ("30", "30 seconds.", "030 seconds", "30 ms", "３0 seconds", "30 Seconds"):
            with self.subTest(invalid=invalid):
                self.assertFalse(grade_answer(case, invalid, actual)["verified_exact"])
        wrong_number = grade_answer(case, "60 seconds", actual)
        self.assertFalse(wrong_number["value_matches"])
        self.assertTrue(wrong_number["unit_matches"])
        wrong_source = grade_answer(case, "30 seconds", [{**citation, "locator": locator + "#L1-L1"}])
        self.assertTrue(wrong_source["citation_id_matches"])
        self.assertFalse(wrong_source["source_url_matches"])
        self.assertFalse(wrong_source["verified_exact"])
        wrong_id = grade_answer(case, "30 seconds", [{**actual[0], "chunk_id": "wrong"}])
        self.assertTrue(wrong_id["source_url_matches"])
        self.assertFalse(wrong_id["citation_id_matches"])

    def test_pinned_source_map_and_synthetic_prose_controls(self):
        manifest = json.loads((HERE / "source-manifest.json").read_bytes())
        for cid, row in self.fixture["records"].items():
            self.assertEqual(row["source"], manifest["spans"][cid]["source_url"])
        for control in json.loads((HERE / "scorer-controls.json").read_bytes())["controls"]:
            with self.subTest(control=control["id"]):
                case = self.cases[control["case_id"]]
                target = case["expected_answer"]
                expected = control["expected"]
                truth, citations = control["asserted_claim"], control["citations"]
                same_scope = truth["scope"] == case["scope"]
                self.assertEqual(same_scope, expected["claim_scope_matches"])
                self.assertEqual(same_scope and truth["value"] == target["value"],
                                 expected["claim_value_correct"])
                self.assertEqual(truth["unit"] == target["unit"], expected["claim_unit_correct"])
                self.assertEqual(f"{target['value']} {target['unit']}" in control["answer"],
                                 expected["literal_value_unit_present"])
                result = grade_answer(case, control["answer"], [{**c, "locator": c["source_url"]} for c in citations])
                self.assertEqual(result["citation_id_matches"], expected["citation_id_correct"])
                self.assertEqual(result["source_url_matches"], expected["source_url_correct"])
                self.assertFalse(expected["grounded_answer"])
                self.assertFalse(result["verified_exact"])

    def test_matched_evidence_removal_and_unfiltered_decoy_are_real(self):
        yes = self.cases["py311-connection-shutdown"]
        no = self.cases["py311-connection-shutdown-removed"]
        self.assertEqual((yes["query"], yes["scope"]), (no["query"], no["scope"]))
        self.assertEqual(set(yes["record_ids"]) - set(no["record_ids"]), {yes["id"]})
        self.assertFalse(set(no["record_ids"]) - set(yes["record_ids"]))
        supported, insufficient = (plan_case(self.fixture, row) for row in (yes, no))
        self.assertEqual(supported["separate_unscoped_top1"], "py311-connection-handshake")
        self.assertEqual(insufficient["separate_unscoped_top1"], "py311-server-shutdown")
        self.assertIsNone(insufficient["pipeline"]["ranking"])
        self.assertEqual(insufficient["pipeline"]["citations"], [])

    def test_actual_cli_positive_and_negative(self):
        for cid in ("py311-connection-shutdown", "py311-connection-shutdown-removed"):
            outcome = subprocess.run([sys.executable, "-B", str(HERE / "audit.py"), "--case", cid],
                                     cwd=ROOT, check=True, capture_output=True)
            row = json.loads(outcome.stdout)
            case = self.cases[cid]
            self.assertEqual(row["pipeline"]["reason"], case["expected_reason"])
            self.assertEqual(row["answer_from_reviewed_plan"], case["expected_answer"])
            self.assertEqual(row["evidence_from_reviewed_plan"], case["expected_citation"])

    def test_recorded_actual_model_envelopes_are_replayed_offline(self):
        self.assertEqual(check(verify_lock()), {"model_calls": 3, "deterministic_stops": 2,
                         "exact_verified": 0, "answer_branches": 3, "model_abstentions": 0,
                         "invalid_responses": 0, "transport_errors": 0})
