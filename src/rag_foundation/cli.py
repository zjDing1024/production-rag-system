"""CLI entry points; corpus-relative paths are explicit and offline."""

import argparse
from pathlib import Path
import sys

from .corpus import build_chunks, canonical_json, digest, load_corpus, read_chunks, write_chunks
from .evaluation import evaluate, load_questions
from .retrieval import BM25


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Offline retrieval foundation, not generated answers")
    sub = parser.add_subparsers(dest="command", required=True)
    ingest = sub.add_parser("ingest", help="verify licensed snapshot and write exact source chunks")
    ingest.add_argument("--root", type=Path, default=Path("."))
    ingest.add_argument("--output", type=Path, default=Path("build/chunks.jsonl"))
    ingest.add_argument("--max-words", type=int, default=180)
    ingest.add_argument("--overlap", type=int, default=40)
    query = sub.add_parser("query", help="return scored source excerpts only")
    query.add_argument("query")
    query.add_argument("--chunks", type=Path, default=Path("build/chunks.jsonl"))
    query.add_argument("-k", type=int, default=5)
    evaluate_parser = sub.add_parser("evaluate", help="rebuild frozen baseline and evaluate evidence retrieval")
    evaluate_parser.add_argument("--root", type=Path, default=Path("."))
    evaluate_parser.add_argument("--questions", type=Path, default=None)
    evaluate_parser.add_argument("--output", type=Path, default=Path("build/evaluation.json"))
    args = parser.parse_args(argv)
    try:
        if args.command == "ingest":
            docs = load_corpus(args.root)
            chunks = build_chunks(docs, args.max_words, args.overlap)
            write_chunks(chunks, args.output)
            print(canonical_json({"documents": len(docs), "chunks": len(chunks),
                                  "output": str(args.output)}), end="")
        elif args.command == "query":
            hits = BM25(read_chunks(args.chunks)).search(args.query, args.k)
            print(canonical_json({"mode": "retrieval-only", "query": args.query,
                                  "answer": None, "results": [h.to_dict() for h in hits]}), end="")
        else:
            path = args.questions or args.root / "data/evaluation/questions.json"
            docs = load_corpus(args.root)
            questions = load_questions(path, docs)
            report = evaluate(build_chunks(docs), questions)
            report["chunking"] = {"max_words": 180, "overlap": 40, "unit": "whitespace words"}
            report["manifest_sha256"] = digest((args.root / "data/manifest.json").read_bytes())
            report["questions_sha256"] = digest(path.read_bytes())
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(canonical_json(report), encoding="utf-8")
            print(canonical_json({"metrics": report["metrics"], "output": str(args.output)}), end="")
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
