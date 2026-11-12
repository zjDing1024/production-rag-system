"""Measure tiny-corpus local build and warm-query costs, without quality tuning."""

import argparse
import json
import math
from pathlib import Path
import platform
import statistics
import time

from rag_foundation.corpus import build_chunks, canonical_json, load_corpus
from rag_foundation.retrieval import BM25


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, default=Path("build/latency.json"))
    args = parser.parse_args()
    start = time.perf_counter()
    docs = load_corpus(args.root)
    chunks = build_chunks(docs)
    index = BM25(chunks)
    build_ms = (time.perf_counter() - start) * 1000
    questions = json.loads((args.root / "data/evaluation/questions.json").read_text())["questions"]
    for q in questions:
        index.search(q["query"])
    times = []
    for _ in range(10):
        for q in questions:
            start = time.perf_counter()
            index.search(q["query"])
            times.append((time.perf_counter() - start) * 1000)
    result = {
        "scope": "one process; tiny pinned corpus; warm search only, no network or generator",
        "python": platform.python_version(), "platform": platform.system(),
        "architecture": platform.machine(), "chunk_count": len(chunks),
        "load_chunk_index_once_ms": build_ms, "warmup_queries": len(questions),
        "measured_queries": len(times), "query_median_ms": statistics.median(times),
        "query_p95_nearest_rank_ms": sorted(times)[math.ceil(.95 * len(times)) - 1],
        "warning": "Non-deterministic wall-clock sample; not a production SLA or scale benchmark.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(canonical_json(result), encoding="utf-8")
    print(canonical_json(result), end="")


if __name__ == "__main__":
    main()
