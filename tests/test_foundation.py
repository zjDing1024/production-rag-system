from dataclasses import replace
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from rag_foundation.corpus import (
    Document, build_chunks, canonical_json, chunk_document, digest,
    load_corpus, read_chunks, write_chunks,
)
from rag_foundation.evaluation import evaluate, is_relevant, load_questions
from rag_foundation.retrieval import BM25, tokenize

ROOT = Path(__file__).resolve().parents[1]


def document(text, id="fixture"):
    return Document(id, "Fixture", text, "https://example.invalid/source", digest(text.encode()), "BSD-3-Clause")


def one_chunk(text, id="fixture"):
    return chunk_document(document(text, id), 100, 0)[0]


class ChunkTests(unittest.TestCase):
    def test_exact_source_slices_and_lines(self):
        doc = document("  α beta\n gamma\n\ndelta epsilon\n")
        chunks = chunk_document(doc, 3, 1)
        self.assertEqual([(c.start_line, c.end_line) for c in chunks], [(1, 2), (2, 4)])
        for c in chunks:
            self.assertEqual(c.text, doc.text[c.start_char:c.end_char])

    def test_word_budget_overlap_and_coverage(self):
        doc = document(" ".join(f"w{i}" for i in range(25)))
        chunks = chunk_document(doc, 7, 2)
        self.assertTrue(all(len(c.text.split()) <= 7 for c in chunks))
        for a, b in zip(chunks, chunks[1:]):
            self.assertEqual(a.text.split()[-2:], b.text.split()[:2])
        self.assertEqual({w for c in chunks for w in c.text.split()}, set(doc.text.split()))

    def test_exact_window_does_not_emit_redundant_tail(self):
        self.assertEqual(len(chunk_document(document("a b c d"), 4, 3)), 1)

    def test_empty_document(self):
        self.assertEqual(chunk_document(document(" \n\t")), [])

    def test_invalid_chunk_parameters(self):
        for size, overlap in [(0, 0), (1, 1), (3, -1), (True, 0), (3, 1.5)]:
            with self.subTest(size=size, overlap=overlap), self.assertRaises(ValueError):
                chunk_document(document("a"), size, overlap)

    def test_ids_stable_and_content_sensitive(self):
        self.assertEqual(one_chunk("a b"), one_chunk("a b"))
        self.assertNotEqual(one_chunk("a b").id, one_chunk("a c").id)

    def test_build_is_sorted_and_rejects_duplicate_ids(self):
        docs = [document("b", "b"), document("a", "a")]
        self.assertEqual(build_chunks(docs), build_chunks(docs[::-1]))
        with self.assertRaises(ValueError):
            build_chunks([docs[0], docs[0]])

    def test_jsonl_roundtrip(self):
        chunks = chunk_document(document("one two 三 four five"), 3, 1)
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "nested/chunks.jsonl"
            write_chunks(chunks, path)
            self.assertEqual(chunks, read_chunks(path))

    def test_invalid_jsonl(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "chunks.jsonl"
            write_chunks([one_chunk("word")] * 2, p)
            with self.assertRaises(ValueError):
                read_chunks(p)

    def test_bad_chunk_spans(self):
        for chunk in [replace(one_chunk("a"), start_char=2), replace(one_chunk("a"), start_line=0)]:
            with tempfile.TemporaryDirectory() as d:
                path = Path(d) / "chunks.jsonl"
                write_chunks([chunk], path)
                with self.assertRaises(ValueError):
                    read_chunks(path)


class CorpusTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        shutil.copytree(ROOT / "data", self.root / "data")
        self.manifest_path = self.root / "data/manifest.json"
        self.manifest = json.loads(self.manifest_path.read_text())

    def tearDown(self):
        self.temp.cleanup()

    def save(self):
        self.manifest_path.write_text(json.dumps(self.manifest))

    def test_six_licensed_sources_and_pinned_blob_hashes(self):
        docs = load_corpus(self.root)
        self.assertEqual(len(docs), 6)
        self.assertEqual(sum(len(d.text.encode()) for d in docs), 99096)
        for row in self.manifest["documents"]:
            b = (self.root / row["path"]).read_bytes()
            blob = __import__("hashlib").sha1(b"blob " + str(len(b)).encode() + b"\0" + b).hexdigest()
            self.assertEqual(row["git_blob_sha"], blob)
            self.assertIn(self.manifest["upstream_commit"], row["source_url"])

    def test_modified_source_rejected(self):
        path = self.root / self.manifest["documents"][0]["path"]
        path.write_text(path.read_text() + "tampered")
        with self.assertRaisesRegex(ValueError, "checksum"):
            load_corpus(self.root)

    def test_modified_license_rejected(self):
        (self.root / self.manifest["license_path"]).write_text("wrong")
        with self.assertRaisesRegex(ValueError, "license checksum"):
            load_corpus(self.root)

    def test_path_escape_rejected(self):
        self.manifest["documents"][0]["path"] = "../outside.txt"
        self.save()
        with self.assertRaisesRegex(ValueError, "escapes"):
            load_corpus(self.root)

    def test_absolute_path_rejected(self):
        self.manifest["documents"][0]["path"] = "/tmp/outside.txt"
        self.save()
        with self.assertRaisesRegex(ValueError, "relative"):
            load_corpus(self.root)

    def test_symlink_escape_rejected(self):
        (self.root / "link.rst").symlink_to(self.root.parent / "outside.rst")
        self.manifest["documents"][0]["path"] = "link.rst"
        self.save()
        with self.assertRaisesRegex(ValueError, "escapes"):
            load_corpus(self.root)

    def test_duplicate_document_id_rejected(self):
        self.manifest["documents"][1]["id"] = self.manifest["documents"][0]["id"]
        self.save()
        with self.assertRaisesRegex(ValueError, "unique"):
            load_corpus(self.root)

    def test_unsupported_license_rejected(self):
        self.manifest["documents"][0]["license"] = "unknown"
        self.save()
        with self.assertRaisesRegex(ValueError, "license|BSD"):
            load_corpus(self.root)

    def test_missing_file_and_unknown_schema_fail(self):
        self.manifest["schema_version"] = 9
        self.save()
        with self.assertRaises(ValueError):
            load_corpus(self.root)
        self.manifest["schema_version"] = 1
        self.manifest["documents"][0]["path"] = "missing.rst"
        self.save()
        with self.assertRaises(FileNotFoundError):
            load_corpus(self.root)


class RetrievalTests(unittest.TestCase):
    def test_token_policy(self):
        self.assertEqual(tokenize("POST app.logger SECRET_KEY Café"), ["post", "app", "logger", "secret_key", "café"])

    def test_bm25_against_hand_calculation(self):
        chunks = [one_chunk("apple apple banana", "a"), one_chunk("banana carrot", "b")]
        hits = BM25(chunks).search("apple")
        expected = math.log(1 + 1.5 / 1.5) * (2 * 2.5) / (2 + 1.5 * (.25 + .75 * 3 / 2.5))
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].chunk.document_id, "a")
        self.assertAlmostEqual(hits[0].score, expected, places=14)

    def test_no_matching_terms_and_empty_inputs(self):
        index = BM25([one_chunk("apple")])
        for query in ["zqxv", "", "!??", "中文问题"]:
            self.assertEqual(index.search(query), [])
        self.assertEqual(BM25([]).search("apple"), [])
        self.assertEqual(BM25([one_chunk("...")]).search("apple"), [])

    def test_repeated_query_terms_not_weighted(self):
        index = BM25([one_chunk("apple banana")])
        self.assertEqual(index.search("apple"), index.search("APPLE apple"))

    def test_tie_breaking_independent_of_input_order(self):
        chunks = [one_chunk("same text", "a"), one_chunk("same text", "b")]
        a, b = BM25(chunks).search("same"), BM25(chunks[::-1]).search("same")
        self.assertEqual(a, b)
        self.assertEqual([h.chunk.id for h in a], sorted(c.id for c in chunks))

    def test_reject_invalid_k(self):
        for k in [0, -1, True, 2.5]:
            with self.subTest(k=k), self.assertRaises(ValueError):
                BM25([]).search("a", k)

    def test_reject_invalid_bm25_parameters(self):
        for k1, b in [(0, .75), (-1, .75), (math.nan, .75), (1.5, math.inf), (1.5, 1.1), (True, .75)]:
            with self.subTest(k1=k1, b=b), self.assertRaises(ValueError):
                BM25([], k1, b)

    def test_duplicate_chunk_ids_rejected(self):
        with self.assertRaises(ValueError):
            BM25([one_chunk("a")] * 2)


class EvaluationTests(unittest.TestCase):
    def test_gold_quotes_exist_and_each_fits_some_chunk(self):
        docs = load_corpus(ROOT)
        questions = load_questions(ROOT / "data/evaluation/questions.json", docs)
        self.assertEqual(len(questions), 22)
        chunks = build_chunks(docs)
        for q in questions:
            if q["answerable"]:
                self.assertTrue(any(is_relevant(c, q) for c in chunks), q["id"])

    def test_wrong_document_or_partial_quote_not_relevant(self):
        q = {"evidence": [{"document_id": "correct", "quote": "alpha beta"}]}
        self.assertFalse(is_relevant(one_chunk("alpha beta", "wrong"), q))
        self.assertFalse(is_relevant(one_chunk("alpha", "correct"), q))
        self.assertTrue(is_relevant(one_chunk("alpha\n beta", "correct"), q))

    def test_metrics_with_known_ranking_and_negative(self):
        chunks = [one_chunk("apple", "a"), one_chunk("banana", "b")]
        questions = [
            {"id": "yes", "query": "apple", "answerable": True,
             "evidence": [{"document_id": "a", "quote": "apple"}]},
            {"id": "miss", "query": "carrot", "answerable": True,
             "evidence": [{"document_id": "b", "quote": "banana"}]},
            {"id": "no", "query": "apple spaceship", "answerable": False, "evidence": []},
        ]
        report = evaluate(chunks, questions)
        self.assertEqual(report["metrics"], {"hit@1": .5, "hit@3": .5, "hit@5": .5,
                                           "mrr@5": .5, "unanswerable_nonempty_rate": 1.0})

    def test_repeated_full_evaluation_is_byte_identical(self):
        docs = load_corpus(ROOT)
        questions = load_questions(ROOT / "data/evaluation/questions.json", docs)
        chunks = build_chunks(docs)
        self.assertEqual(canonical_json(evaluate(chunks, questions)), canonical_json(evaluate(chunks, questions)))

    def test_stale_gold_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "questions.json"
            p.write_text(json.dumps({"schema_version": 1, "questions": [
                {"id": "bad", "query": "a", "answerable": True,
                 "evidence": [{"document_id": "fixture", "quote": "missing"}]}]}))
            with self.assertRaisesRegex(ValueError, "gold evidence"):
                load_questions(p, [document("a")])

    def test_cli_end_to_end_and_no_generated_answer(self):
        with tempfile.TemporaryDirectory() as d:
            chunks = Path(d) / "chunks.jsonl"
            def run(*args):
                result = subprocess.run([sys.executable, "-m", "rag_foundation", *args],
                                        cwd=ROOT, capture_output=True, text=True, check=True)
                return json.loads(result.stdout)
            result = run("ingest", "--root", str(ROOT), "--output", str(chunks))
            self.assertEqual(result["documents"], 6)
            result = run("query", "test client live server", "--chunks", str(chunks), "-k", "3")
            self.assertEqual(result["mode"], "retrieval-only")
            self.assertIsNone(result["answer"])
            self.assertEqual(len(result["results"]), 3)
            self.assertIn("#L", result["results"][0]["citation"])
            output = Path(d) / "report.json"
            run("evaluate", "--root", str(ROOT), "--output", str(output))
            self.assertEqual(json.loads(output.read_text())["question_count"], 22)

    def test_cli_invalid_input_nonzero_exit(self):
        result = subprocess.run([sys.executable, "-m", "rag_foundation", "ingest", "--max-words", "0"],
                                cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn("positive integer", result.stderr)


if __name__ == "__main__":
    unittest.main()
