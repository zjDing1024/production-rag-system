"""Exercise orchestration and citation policy, not inference or entailment."""

from dataclasses import asdict
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from rag_foundation.corpus import digest
from rag_foundation.safe_document_agent import DocumentAgent, INTENTS, MAX_CHUNKS, MAX_CORPUS_CHARACTERS

ROOT = Path(__file__).resolve().parents[1]


class ReadOnlyAgentTests(unittest.TestCase):
    def setUp(self):
        self.agent = DocumentAgent()

    def test_two_versions_and_exact_evidence(self):
        for r, expected, source_tag in (("express-4-default", "extended", "1faf2289"),
                                         ("express-5-default", "simple", "cd7d4397")):
            with self.subTest(r=r):
                result = self.agent.answer(r)
                self.assertEqual(result["status"], "answered")
                self.assertEqual(result["answer"]["value"], expected)
                self.assertEqual(result["bound_scope"], asdict(INTENTS[r].scope))
                citation, = result["citations"]
                self.assertIn(source_tag, citation["source"])
                h = digest(citation["quote"].encode("utf-8"))
                self.assertEqual(citation["summary_sha256"], h)
                self.assertEqual(result["model_calls"], 0)

    def test_same_version_wrong_field_never_reaches_retrieval(self):
        from rag_foundation.scope_gate import Scope
        wrong = Scope("documentation", "Express", "some-other-setting.default", "5.1.0")
        with patch.object(self.agent._retriever, "answer") as retrieve:
            result = self.agent.answer("express-5-default", expected_scope=wrong)
            self.assertEqual(result["reason"], "intent_scope_mismatch")
            self.assertEqual(result["retrieval_attempts"], 0)
            self.assertEqual(result["citations"], [])
            retrieve.assert_not_called()

    def test_scope_preserving_retry_and_budget(self):
        with patch.object(self.agent._retriever, "answer", wraps=self.agent._retriever.answer) as retrieve:
            success = self.agent.answer("cpython-color-retry")
        self.assertEqual([a.args[1] for a in retrieve.call_args_list], [INTENTS["cpython-color-retry"].scope] * 2)
        self.assertEqual(success["ranking_attempts"], 2)
        steps = [t for t in success["trace"] if t["event"] == "retrieve"]
        self.assertEqual([t["reason"] for t in steps], ["no_lexical_candidates", "generator_not_requested"])
        self.assertEqual([t["lexical_hits"] for t in steps], [0, 1])
        denied = self.agent.answer("cpython-color-retry", max_retrievals=1)
        self.assertEqual((denied["reason"], denied["retrieval_attempts"]), ("retrieval_budget_exhausted", 1))
        self.assertIsNone(denied["answer"])

    def test_scope_gate_catches_zero_overlap_conflict_before_ranking(self):
        hits = self.agent._index.bm25.search("DemoBox timeout")
        self.assertNotIn("demo-timeout-b", [hit.chunk.id for hit in hits])
        with patch.object(self.agent._index.bm25, "search") as rank:
            result = self.agent.answer("demo-timeout-conflict")
        self.assertEqual(result["reason"], "reviewed_value_conflict")
        self.assertEqual(result["trace"][1]["matched_ids"], ["demo-timeout-a", "demo-timeout-b"])
        self.assertEqual(result["retrieval_attempts"], 1)
        rank.assert_not_called()

    def test_packing_stop_is_not_retried(self):
        result = self.agent.answer("cpython-color-retry", context_characters=1)
        self.assertEqual(result["reason"], "context_budget_exhausted")
        self.assertEqual(result["retrieval_attempts"], 2)
        self.assertEqual(result["citations"], [])

    def test_distinct_missing_unknown_unreviewed(self):
        for request, why, attempts in (("demo-retries-missing", "no_matching_scope", 1),
                                       ("demo-queue-unreviewed", "missing_reviewed_claim", 1),
                                       ("unregistered", "unknown_intent", 0)):
            r = self.agent.answer(request)
            self.assertEqual((r["reason"], r["retrieval_attempts"]), (why, attempts))
            self.assertEqual((r["answer"], r["citations"], r["ranking_attempts"]), (None, [], 0))

    def test_known_wrong_id_cannot_be_cited(self):
        old = INTENTS["express-4-default"]
        cross = self.agent._retriever.answer(old.query, old.scope, k=1, scope_gate=True)
        with patch.object(self.agent._retriever, "answer", return_value=cross):
            r = self.agent.answer("express-5-default")
            self.assertEqual(r["reason"], "citation_scope_mismatch")
            self.assertEqual(r["citations"], [])

    def test_known_id_with_changed_reference_cannot_be_cited(self):
        t = INTENTS["express-5-default"]
        forged = self.agent._retriever.answer(t.query, t.scope, k=1, scope_gate=True)
        forged["context"][0]["citation"] = "synthetic://unrelated_source"
        with patch.object(self.agent._retriever, "answer", return_value=forged):
            r = self.agent.answer("express-5-default")
            self.assertEqual(r["reason"], "citation_provenance_mismatch")
            self.assertIsNone(r["answer"])

    def test_caps_cannot_be_relaxed_by_request(self):
        self.assertLessEqual(len(self.agent._index.chunks), MAX_CHUNKS)
        self.assertLessEqual(sum(len(c.text) for c in self.agent._index.chunks), MAX_CORPUS_CHARACTERS)
        for kwargs in ({"max_retrievals": True}, {"max_retrievals": 3}, {"context_characters": 513}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.agent.answer("express-5-default", **kwargs)

    def test_no_transport_or_generation_during_retry(self):
        with patch("socket.socket", side_effect=AssertionError("no socket")), \
             patch("rag_foundation.generation.LocalGenerator.generate", side_effect=AssertionError("no model")):
            self.assertEqual(self.agent.answer("cpython-color-retry")["status"], "answered")

    def test_cli_exact_transcript(self):
        checked = subprocess.run([sys.executable, str(ROOT / "experiments/read-only-agent-v1/replay.py"),
                                  "--check"], cwd=ROOT, capture_output=True, text=True, timeout=20)
        self.assertEqual(checked.returncode, 0, checked.stderr)
