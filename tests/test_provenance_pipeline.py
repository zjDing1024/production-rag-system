from dataclasses import asdict, replace
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock

from rag_foundation.corpus import Chunk, digest, write_chunks
from rag_foundation.provenance_pipeline import ProvenancePipeline, render_provenance
from rag_foundation.scope_gate import Scope
from rag_foundation.scoped_pipeline import ClaimIndex, ScopedGenerationPipeline, chunks_fingerprint

ROOT = Path(__file__).resolve().parents[1]
SCOPE = Scope("documentation", "Example", "interval.default", "1.0.0")
ANCHOR = "https://example.test/repo/docs.md#L93-L96"
UNANCHORED = "https://example.test/repo/full.md?q=%23"
TEXT = "Reviewed default interval: 30 seconds."


def chunk(cid, source):
    return Chunk(cid, cid, "Original fixture", TEXT, source, digest(TEXT.encode()),
                 "MIT", 50, 50 + len(TEXT), 9, 11)


def catalog(chunks):
    return {
        "schema_version": 1, "complete": True, "chunks_sha256": chunks_fingerprint(chunks),
        "entries": [{"chunk_id": c.id, "scope": asdict(SCOPE), "claim": {
            "reviewed": True, "chunk_text_sha256": c.source_sha256, "value_type": "integer",
            "value": 30, "unit": "seconds", "start_char": 0, "end_char": len(TEXT), "quote": TEXT,
        }} for c in chunks],
    }


class ProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.chunks = [chunk("a", ANCHOR), chunk("b", UNANCHORED)]
        self.index = ClaimIndex(self.chunks, catalog(self.chunks))

    def test_source_fragments_are_distinct_from_local_spans(self):
        upstream, local = map(render_provenance, self.chunks)
        self.assertEqual(upstream["locator"], ANCHOR)
        self.assertEqual(upstream["locator_kind"], "upstream_fragment")
        self.assertEqual(local["locator"], UNANCHORED + "#L9-L11")
        self.assertEqual(local["source_url"], UNANCHORED)
        self.assertEqual(local["locator_kind"], "local_line_range")
        self.assertEqual(local["local_span"], upstream["local_span"])
        self.assertEqual(upstream["local_span"]["start_char"], 50)
        chapter = "https://example.test/docs?rev=1#timeout-default"
        self.assertEqual(render_provenance(chunk("c", chapter))["locator"], chapter)
        self.assertEqual(render_provenance(chunk("d", UNANCHORED + "#"))["locator"],
                         UNANCHORED + "#L9-L11")

    def test_rank_context_and_final_reuse_identical_locators(self):
        model = Mock()
        model.generate.return_value = {"status": "answered", "reason": "contract_valid",
                                       "answer": "30 seconds", "citation_ids": ["b", "a"]}
        result = ProvenancePipeline(self.index, model).answer("interval default", SCOPE, k=2, scope_gate=True)
        expected = [ANCHOR, UNANCHORED + "#L9-L11"]
        for hits in (result["ranking"]["ranked_hits"], result["context"],
                     model.generate.call_args.args[1]):
            self.assertEqual([hit["citation"] for hit in hits], expected)
            self.assertEqual([hit["provenance"]["locator"] for hit in hits], expected)
        self.assertEqual([row["locator"] for row in result["citations"]], expected[::-1])
        self.assertEqual([row["chunk_id"] for row in result["citations"]], ["b", "a"])
        self.assertEqual(result["semantic_support"], "unverified")

    def test_output_citations_must_reference_packed_not_merely_ranked(self):
        model = Mock()
        model.generate.return_value = {"status": "answered", "reason": "contract_valid",
                                       "answer": "30 seconds", "citation_ids": ["b"]}
        with self.assertRaisesRegex(ValueError, "packed context"):
            ProvenancePipeline(self.index, model).answer("interval default", SCOPE, k=2,
                                                         context_characters=len(TEXT), scope_gate=True)

    def test_stop_and_abstention_dont_claim_final_sources(self):
        model = Mock()
        model.generate.return_value = {"status": "evidence_abstained", "reason": "model_abstention",
                                       "answer": None, "citation_ids": []}
        pipeline = ProvenancePipeline(self.index, model)
        negative = pipeline.answer("interval default", replace(SCOPE, version="2.0.0"), scope_gate=True)
        self.assertEqual(negative["reason"], "no_matching_scope")
        self.assertIsNone(negative["ranking"])
        self.assertEqual(negative["citations"], [])
        model.generate.assert_not_called()
        abstained = pipeline.answer("interval default", SCOPE, k=1, scope_gate=True)
        self.assertEqual(abstained["reason"], "model_abstention")
        self.assertEqual(abstained["citations"], [])
        self.assertEqual(abstained["context"][0]["citation"], ANCHOR)

    def test_legacy_renderer_unchanged(self):
        result = ScopedGenerationPipeline(self.index).answer("interval default", SCOPE, k=1)
        self.assertEqual(result["context"][0]["citation"], ANCHOR + "#L9-L11")
        self.assertNotIn("provenance", result["context"][0])

    def test_actual_offline_cli(self):
        with tempfile.TemporaryDirectory() as work:
            chunks, cat, req = (Path(work) / key for key in ("chunks", "catalog", "request"))
            write_chunks(self.chunks, chunks)
            cat.write_text(json.dumps(catalog(self.chunks)), encoding="utf-8")
            req.write_text(json.dumps({"query": "interval default", "scope": asdict(SCOPE)}),
                           encoding="utf-8")
            run = subprocess.run(
                [sys.executable, "-B", "-m", "rag_foundation.provenance_pipeline",
                 "--chunks", str(chunks), "--catalog", str(cat), "--request", str(req),
                 "--scope-gate", "-k", "2"], cwd=ROOT,
                env={"PYTHONPATH": str(ROOT / "src")}, check=True, capture_output=True)
        result = json.loads(run.stdout)
        self.assertEqual(result["status"], "planned")
        self.assertFalse(result["generator_called"])
        self.assertEqual([h["citation"] for h in result["context"]], [ANCHOR, UNANCHORED + "#L9-L11"])
        self.assertEqual(result["citations"], [])
