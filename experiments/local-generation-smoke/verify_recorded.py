"""Offline consistency checks of the saved first run, not a new model evaluation."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def format_checks(case_id, content):
    """Only literal output-contract checks; this is NOT a semantic answer judge."""
    if case_id == "unsupported":
        return {"exact_abstention_marker": content == "INSUFFICIENT_EVIDENCE"}
    return {"nonempty_answer": bool(content.strip()), "required_citation": "[S1]" in content}


def verify_recorded(root=ROOT):
    summary = json.loads((root / "recorded/summary.json").read_text(encoding="utf-8"))
    for filename, key in [("cases.json", "cases_sha256"), ("run_smoke.py", "runner_sha256")]:
        if hashlib.sha256((root / filename).read_bytes()).hexdigest() != summary[key]:
            raise ValueError(f"Recorded run input changed: {filename}")
    cases = json.loads((root / "cases.json").read_text(encoding="utf-8"))["cases"]
    expected = {case["id"]: case["expected_behavior"] for case in cases}
    if [x["id"] for x in cases] != [x["id"] for x in summary["requests"]]:
        raise ValueError("Recorded request order or case count changed")
    results = []
    for request in summary["requests"]:
        raw_path = root / "recorded" / f"{request['id']}-response.raw.json"
        raw = raw_path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != request["raw_sha256"]:
            raise ValueError(f"Raw response changed: {request['id']}")
        response = json.loads(raw)
        if request["content"] != response["choices"][0]["message"]["content"]:
            raise ValueError("Summary answer does not match raw response")
        if request["expected_behavior"] != expected[request["id"]]:
            raise ValueError("Summary does not match pre-written expectation")
        checks = format_checks(request["id"], request["content"])
        strict = all(checks.values()) and request["human_semantic_expectation_met"]
        if request["strict_pass"] != strict:
            raise ValueError("Inconsistent strict-pass assessment")
        results.append({"id": request["id"], "format_checks": checks, "strict_pass": strict})
    passed = sum(result["strict_pass"] for result in results)
    if summary["strict_pass_count"] != passed or summary["case_count"] != len(results):
        raise ValueError("Inconsistent aggregate counts")
    return {"record_integrity": "verified", "scope": "saved smoke run, no model execution",
            "strict_pass_count": passed, "case_count": len(results), "results": results}


if __name__ == "__main__":
    print(json.dumps(verify_recorded(), ensure_ascii=False, indent=2))
