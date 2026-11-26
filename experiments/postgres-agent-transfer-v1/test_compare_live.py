"""Regression tests for the frozen scoring and actual receipt replay."""
import unittest

from compare_live import annotation, check, verify_lock


class PostgresLiveReceiptTests(unittest.TestCase):
    def row(self, answer, chunk):
        return {"generator_called": True, "status": "answered", "reason": "contract_valid",
                "context": [{"chunk_id": chunk}],
                "generation": {"answer": answer, "citation_ids": [chunk]}}

    def test_exact_value_does_not_make_wrong_evidence_supported(self):
        result = annotation("pg17-neighbors-only", self.row(" 0 ms. ", "pg17-idle-default"))
        self.assertTrue(result["canonical_zero_ms"])
        self.assertIs(result["truth_of_zero_ms_for_pinned_question"], True)
        self.assertFalse(result["cites_requested_setting_default"])
        self.assertEqual(result["classification"], "unsupported_answer")

    def test_version_without_setting_is_not_zero_default(self):
        result = annotation("pg16-neighbors-only", self.row("0 milliseconds", "pg16-idle-default"))
        self.assertIs(result["truth_of_zero_ms_for_pinned_question"], False)
        self.assertEqual(result["classification"], "unsupported_answer")

    def test_exact_value_and_exact_origin_are_jointly_required(self):
        cid = "pg17-transaction-default"
        result = annotation("pg17-transaction", self.row("0 ms", cid))
        self.assertEqual(result["classification"], "correct_cited_supported")
        result = annotation("pg17-transaction", self.row("The default is 0 milliseconds.", cid))
        self.assertEqual(result["classification"], "noncanonical_answer")
        self.assertIsNone(result["truth_of_zero_ms_for_pinned_question"])

    def test_citation_must_be_from_supplied_context(self):
        row = self.row("0 ms", "pg17-idle-default")
        row["generation"]["citation_ids"] = ["pg17-transaction-default"]
        with self.assertRaises(ValueError):
            annotation("pg17-transaction", row)

    def test_deterministic_stop_and_model_abstention_differ(self):
        stopped = annotation("pg17-exception-only", {"generator_called": False,
                            "status": "not_run", "reason": "no_matching_scope", "generation": None})
        abstained = annotation("pg17-exception-only", {"generator_called": True,
                              "status": "evidence_abstained", "reason": "model_abstention",
                              "generation": {"answer": None, "citation_ids": []}})
        self.assertEqual(stopped["classification"], "deterministic_stop")
        self.assertEqual(abstained["classification"], "model_abstention")

    def test_full_offline_receipt(self):
        result = check(verify_lock())
        self.assertEqual(result["unscoped"]["model_calls"], 5)
        self.assertEqual(result["unscoped"]["unsupported_answer"], 3)
        self.assertEqual(result["scoped"]["model_calls"], 2)
        self.assertEqual(result["scoped"]["deterministic_stop"], 3)
        for arm in ("unscoped", "scoped"):
            self.assertEqual(result[arm]["correct_cited_supported"], 0)
            self.assertEqual(result[arm]["noncanonical_answer"], 2)
            self.assertEqual(result[arm]["model_abstention"], 0)
            self.assertEqual(result[arm]["transport_error"], 0)
            self.assertEqual(result[arm]["invalid_response"], 0)
