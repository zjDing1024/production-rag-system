"""Invoke the real module CLI on a frozen acceptance matrix without a model."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "src"))

from rag_foundation.corpus import canonical_json

# Case labels and expected reasons are independent of the agent implementation.
CASES = (
    ("old_release", ("express-4-default",), "reviewed_claim_cited", 1, 1, "extended", "express-4"),
    ("new_release", ("express-5-default",), "reviewed_claim_cited", 1, 1, "simple", "express-5"),
    ("retry_rescues", ("cpython-color-retry",), "reviewed_claim_cited", 2, 2, "True", "cpython-color"),
    ("retry_budget", ("cpython-color-retry", "--max-retrievals", "1"), "retrieval_budget_exhausted", 1, 1, None, None),
    ("packing_budget", ("express-5-default", "--context-characters", "12"), "context_budget_exhausted", 1, 1, None, None),
    ("conflicting_value", ("demo-timeout-conflict",), "reviewed_value_conflict", 1, 0, None, None),
    ("missing_scope", ("demo-retries-missing",), "no_matching_scope", 1, 0, None, None),
    ("unreviewed_claim", ("demo-queue-unreviewed",), "missing_reviewed_claim", 1, 0, None, None),
    ("misbound_release", ("express-5-default", "--expect-scope-of", "express-4-default"), "intent_scope_mismatch", 0, 0, None, None),
    ("unknown_intent", ("unregistered",), "unknown_intent", 0, 0, None, None),
)


def replay():
    rows = []
    for label, args, reason, attempts, ranks, value, cid in CASES:
        run = subprocess.run(
            [sys.executable, "-m", "rag_foundation.safe_document_agent", *args],
            cwd=ROOT, env={**os.environ, "PYTHONPATH": str(ROOT / "src"), "PYTHONDONTWRITEBYTECODE": "1"},
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, timeout=10,
        )
        observed = json.loads(run.stdout)
        answer = observed["answer"]
        cites = observed["citations"]
        baseline = (reason, attempts, ranks, value, [cid] if cid else [], 0)
        actual = (observed["reason"], observed["retrieval_attempts"], observed["ranking_attempts"],
                  answer and answer["value"], [cite["chunk_id"] for cite in cites], observed["model_calls"])
        if actual != baseline or observed["status"] != ("answered" if cid else "stopped"):
            raise ValueError(f"{label} did not match the frozen oracle: {actual!r}")
        rows.append({"case": label, "arguments": list(args), "result": observed})
    metrics = {
        "cases": len(rows),
        "cited_answers": sum(r["result"]["status"] == "answered" for r in rows),
        "explicit_stops": sum(r["result"]["status"] == "stopped" for r in rows),
        "retrieval_attempts": sum(r["result"]["retrieval_attempts"] for r in rows),
        "ranking_attempts": sum(r["result"]["ranking_attempts"] for r in rows),
        "max_retrievals_seen": max(r["result"]["retrieval_attempts"] for r in rows),
        "model_calls": sum(r["result"]["model_calls"] for r in rows),
    }
    return {"method": "actual CLI + real local BM25, no generated answers", "metrics": metrics, "rows": rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    content = canonical_json(replay())
    if args.check:
        if (HERE / "report.json").read_bytes() != content.encode("utf-8"):
            raise ValueError("recorded CLI acceptance transcript changed")
        print("Ten-case offline Agent CLI matches recorded transcript.")
    else:
        print(content, end="")


if __name__ == "__main__":
    main()
