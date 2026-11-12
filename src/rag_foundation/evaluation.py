"""Small, authored development evaluation, never a held-out quality claim."""

from dataclasses import asdict
import json
from pathlib import Path

from .corpus import Chunk, Document, canonical_json, digest
from .retrieval import BM25, TOKENIZER


def normalize_space(text: str) -> str:
    return " ".join(text.split())


def load_questions(path: Path, documents: list[Document]) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise ValueError("unsupported evaluation schema")
    questions = payload["questions"]
    if not questions:
        raise ValueError("evaluation is empty")
    texts = {d.id: normalize_space(d.text) for d in documents}
    ids = set()
    for q in questions:
        if not isinstance(q["id"], str) or not q["id"] or q["id"] in ids:
            raise ValueError("question IDs must be nonempty and unique")
        ids.add(q["id"])
        if not isinstance(q["query"], str) or not q["query"].strip():
            raise ValueError("question query must be nonempty text")
        if type(q["answerable"]) is not bool:
            raise ValueError("answerable must be boolean")
        evidence = q["evidence"]
        if q["answerable"] != bool(evidence):
            raise ValueError("answerability and evidence disagree")
        for e in evidence:
            quote = normalize_space(e["quote"])
            if not quote or quote not in texts.get(e["document_id"], ""):
                raise ValueError(f"gold evidence not found in pinned corpus: {q['id']}")
    return questions


def is_relevant(chunk: Chunk, question: dict) -> bool:
    return any(e["document_id"] == chunk.document_id
               and normalize_space(e["quote"]) in normalize_space(chunk.text)
               for e in question["evidence"])


def evaluate(chunks: list[Chunk], questions: list[dict], k: int = 5) -> dict:
    index = BM25(chunks)
    rows = []
    answerable = []
    negatives = []
    for q in questions:
        hits = index.search(q["query"], k)
        ranks = [rank for rank, hit in enumerate(hits, 1) if is_relevant(hit.chunk, q)]
        rank = min(ranks) if ranks else None
        row = {"id": q["id"], "query": q["query"], "answerable": q["answerable"],
               "first_relevant_rank": rank, "returned_count": len(hits),
               "retrieved": [{"chunk_id": hit.chunk.id, "document_id": hit.chunk.document_id,
                              "score": hit.score, "citation": hit.chunk.citation,
                              "relevant": is_relevant(hit.chunk, q)} for hit in hits]}
        rows.append(row)
        (answerable if q["answerable"] else negatives).append(row)
    metrics = {}
    if answerable:
        for cutoff in sorted({1, 3, k}):
            if cutoff <= k:
                metrics[f"hit@{cutoff}"] = sum(r["first_relevant_rank"] is not None
                    and r["first_relevant_rank"] <= cutoff for r in answerable) / len(answerable)
        metrics[f"mrr@{k}"] = sum(1 / r["first_relevant_rank"] if r["first_relevant_rank"] else 0
                                  for r in answerable) / len(answerable)
    if negatives:
        metrics["unanswerable_nonempty_rate"] = sum(r["returned_count"] > 0 for r in negatives) / len(negatives)
    return {"schema_version": 1, "scope": "retrieval-only authored development set",
            "generator": None, "tokenizer": TOKENIZER, "bm25": {"k1": 1.5, "b": 0.75},
            "k": k, "chunk_count": len(chunks), "question_count": len(questions),
            "answerable_count": len(answerable), "unanswerable_count": len(negatives),
            "chunks_sha256": digest(canonical_json([asdict(c) for c in chunks]).encode()),
            "metrics": metrics, "results": rows}
