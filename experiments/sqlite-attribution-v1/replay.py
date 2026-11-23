"""Exercise the real indexed pipeline with a fixture-only scope binding."""

import argparse
from dataclasses import asdict
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "src"))

from fixture import EVIDENCE, FIXTURE_ID, QUESTION, TARGET, WRONG_FIELD, WRONG_OBJECT, runtime_oracle
from rag_foundation.corpus import Chunk, canonical_json, digest
from rag_foundation.scope_gate import Scope
from rag_foundation.scoped_pipeline import ClaimIndex, ScopedGenerationPipeline, chunks_fingerprint
from rag_foundation.version_bound import answer_with_version_binding, check_version

VERSION = "3.46.1"
TRUSTED_REQUEST = {FIXTURE_ID: (QUESTION, TARGET)}
ALL_EVIDENCE = ("main-hidden", "temp-hidden", "main-cid")
CASES = (
    ("supported", TARGET, ALL_EVIDENCE, "main-hidden"),
    ("wrong_object_same_value", WRONG_OBJECT, ALL_EVIDENCE, "temp-hidden"),
    ("wrong_field_same_value", WRONG_FIELD, ALL_EVIDENCE, "main-cid"),
    ("missing_field", TARGET, ("table-info",), None),
)


def scope(identity):
    # These are versioned synthetic documentation records, not runtime events.
    return Scope("documentation", "SQLite", identity.key, VERSION)


def pipeline_for(ids):
    chunks, entries = [], []
    for cid in ids:
        identity, value, content = EVIDENCE[cid]
        text_hash = digest(content.encode("utf-8"))
        chunk = Chunk(cid, "sqlite-fixture-" + cid, "Original synthetic SQLite summary", content,
                      "synthetic://sqlite-attribution-v1/" + cid, text_hash, "MIT", 0, len(content), 1, 1)
        chunks.append(chunk)
        entries.append({
            "chunk_id": cid,
            "scope": asdict(scope(identity)),
            "claim": {
                "reviewed": True, "chunk_text_sha256": text_hash,
                "value_type": "integer" if type(value) is int else "string",
                "unit": "pragma_field" if type(value) is int else "presence",
                "value": value, "start_char": 0, "end_char": len(content), "quote": content,
            },
        })
    return ScopedGenerationPipeline(ClaimIndex(chunks, {
        "schema_version": 1, "complete": True,
        "chunks_sha256": chunks_fingerprint(chunks), "entries": entries,
    }))


def run_bound(pipeline, fixture_id, question, caller_scope):
    trusted = TRUSTED_REQUEST.get(fixture_id)
    if trusted is None or question != trusted[0]:
        reason = "unknown_fixture_request"
    elif caller_scope != scope(trusted[1]):
        reason = "fixture_scope_mismatch"
    else:
        return answer_with_version_binding(pipeline, question, caller_scope, k=1)
    return {"status": "not_run", "reason": reason, "pipeline": None, "generator_called": False}


def project(arm):
    outcome = arm["pipeline"]
    selected = [] if outcome is None else [hit["chunk_id"] for hit in outcome["context"]]
    cit = EVIDENCE[selected[0]] if selected else None
    lexical = None
    if outcome is not None and outcome["ranking"] is not None:
        lexical = outcome["ranking"]["lexical_candidate_count"]
    return {
        "status": arm["status"], "reason": arm["reason"], "packed_ids": selected,
        "ranking_performed": lexical is not None, "scope_lexical_hits": lexical,
        "generator_called": arm["generator_called"],
        "candidate_value": cit[1] if cit else None,
        "numeric_exact_match": type(cit[1]) is int and cit[1] == 3 if cit else None,
        "citation_tuple": asdict(cit[0]) if cit else None,
        "citation_support": cit[0] == TARGET if cit else None,
    }


def replay():
    rows = []
    for label, caller, corpus, expected_id in CASES:
        p = pipeline_for(corpus)
        caller_scope = scope(caller)
        version_result = check_version(QUESTION, caller_scope)
        if version_result["status"] != "bound":
            raise ValueError("the controlled caller must pass version-only inspection")
        baseline, bound = (
            project(answer_with_version_binding(p, QUESTION, caller_scope, k=1)),
            project(run_bound(p, FIXTURE_ID, QUESTION, caller_scope)),
        )
        if baseline["packed_ids"] != ([expected_id] if expected_id else []):
            raise ValueError("fixture no longer reproduces expected packing")
        rows.append({
            "case": label, "caller": asdict(caller), "catalog_ids": list(corpus),
            "version_check": version_result["reason"],
            "baseline": baseline, "fixture_bound": bound,
        })
    metrics = {}
    for arm in ("baseline", "fixture_bound"):
        plans = [row[arm] for row in rows]
        metrics[arm] = {
            "correct_with_support": sum(p["numeric_exact_match"] is True and p["citation_support"] is True for p in plans),
            "numeric_match_without_support": sum(p["numeric_exact_match"] is True and p["citation_support"] is False for p in plans),
            "fixture_blocks": sum(p["reason"] == "fixture_scope_mismatch" for p in plans),
            "missing_scope_stops": sum(p["reason"] == "no_matching_scope" for p in plans),
            "generator_calls": sum(p["generator_called"] for p in plans),
        }
    return {"question": QUESTION, "target": asdict(TARGET), "expected_value": 3,
            "fixture_id": FIXTURE_ID, "rows": rows, "metrics": metrics,
            "method": "actual BM25, no model; numeric score applies to candidate metadata, not an answer"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    operation = parser.add_mutually_exclusive_group()
    operation.add_argument("--check", action="store_true")
    operation.add_argument("--oracle", action="store_true")
    args = parser.parse_args()
    if args.oracle:
        print(canonical_json(runtime_oracle()), end="")
        return
    rendered = canonical_json(replay())
    if args.check:
        if (HERE / "replay.json").read_bytes() != rendered.encode("utf-8"):
            raise ValueError("SQLite attribution replay differs from recorded artifact")
        print("SQLite attribution replay matches recorded artifact (no model).")
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
