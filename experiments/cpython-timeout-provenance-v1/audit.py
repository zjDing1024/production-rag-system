"""Attest exact source anchors and typed CPython timeout evidence offline."""
import argparse
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "src"))

from rag_foundation.corpus import canonical_json, digest
from rag_foundation.provenance_pipeline import ProvenancePipeline
from rag_foundation.safe_document_agent import Record, _build_index
from rag_foundation.scope_gate import Scope

BARE_SECONDS = re.compile(r"(0|[1-9][0-9]{0,5}) seconds", re.ASCII)


def load_fixture():
    fixture = HERE / "oracle.json"
    content = fixture.read_bytes()
    if digest(content) != (HERE / "oracle.sha256").read_text().strip():
        raise ValueError("frozen fixture checksum mismatch")
    return json.loads(content)


def index_for(fixture, case):
    records = fixture["records"]
    return _build_index([
        Record(cid, Scope.from_dict(records[cid]["scope"]), records[cid]["value"],
               records[cid]["unit"], records[cid]["text"], records[cid]["source"])
        for cid in case["record_ids"]
    ])


def plan_case(fixture, case):
    index = index_for(fixture, case)
    scope = Scope.from_dict(case["scope"])
    outcome = ProvenancePipeline(index).answer(case["query"], scope, k=1, scope_gate=True)
    unscoped = index.bm25.search(case["query"], 1)
    if (outcome["status"] != case["expected_status"] or outcome["reason"] != case["expected_reason"]
            or outcome["generator_called"] or outcome["citations"]):
        raise ValueError(f"{case['id']} violated frozen stop or plan contract")
    answer = citation = None
    if outcome["status"] == "planned":
        if len(outcome["context"]) != 1 or len(outcome["ranking"]["ranked_hits"]) != 1:
            raise ValueError("planned row requires exactly one ranked and packed hit")
        hit, ranked = outcome["context"][0], outcome["ranking"]["ranked_hits"][0]
        prov = hit["provenance"]
        if (hit != ranked or hit["citation"] != prov["source_url"]
                or prov["locator"] != prov["source_url"] or prov["locator_kind"] != "upstream_fragment"
                or prov["locator"].count("#") != 1):
            raise ValueError("ranked and packed evidence must agree with the anchored source URL")
        claim = index.claims[hit["chunk_id"]]
        if claim is None or type(claim.value) is not int or index.scopes[hit["chunk_id"]] != scope:
            raise ValueError("unreviewed, untyped or mismatched scope was packed")
        answer = {"value_type": claim.value_type, "value": claim.value, "unit": claim.unit}
        citation = {"chunk_id": hit["chunk_id"], "source_url": prov["source_url"]}
    elif outcome["ranking"] is not None or outcome["context"]:
        raise ValueError("expected rejection before ranking and packing")
    if (answer != case["expected_answer"] or citation != case["expected_citation"] or
            (answer is not None and type(case["expected_answer"]["value"]) is not int)):
        raise ValueError(f"{case['id']} disagrees with typed fixture or source identity")
    return {"case": case["id"], "answer_from_reviewed_plan": answer, "evidence_from_reviewed_plan": citation,
            "model_calls": 0, "pipeline": outcome,
            "separate_unscoped_top1": unscoped[0].chunk.id if unscoped else None}


def grade_answer(case, answer, citations):
    """Strict display rubric for one scoped request, not a prose entailment oracle."""
    expected = case["expected_answer"]
    gold = case["expected_citation"]
    pair = BARE_SECONDS.fullmatch(answer.strip()) if type(answer) is str else None
    if expected is None or gold is None:
        raise ValueError("only a registered answerable case may be scored")
    value = int(pair.group(1)) if pair else None
    unit = "seconds" if pair else None
    citation = citations[0] if len(citations) == 1 else {}
    results = {
        "bare_integer_value": value, "bare_unit": unit,
        "value_matches": value == expected["value"], "unit_matches": unit == expected["unit"],
        "citation_id_matches": citation.get("chunk_id") == gold["chunk_id"],
        "source_url_matches": citation.get("source_url") == gold["source_url"]
                              and citation.get("locator") == gold["source_url"],
    }
    results["verified_exact"] = all(results[key] for key in (
        "value_matches", "unit_matches", "citation_id_matches", "source_url_matches"))
    return results


def build_report(fixture):
    rows = [plan_case(fixture, case) for case in fixture["cases"]]
    return {"rows": rows, "planned": sum(row["pipeline"]["status"] == "planned" for row in rows),
            "stopped_before_ranking": sum(row["pipeline"]["ranking"] is None for row in rows),
            "model_calls": 0, "separate_unscoped_top1_rows": sum(bool(row["separate_unscoped_top1"]) for row in rows)}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    mode = cli.add_mutually_exclusive_group()
    mode.add_argument("--case")
    mode.add_argument("--check", action="store_true")
    args = cli.parse_args()
    fixture = load_fixture()
    if args.case:
        case = next((case for case in fixture["cases"] if case["id"] == args.case), None)
        if case is None:
            cli.error("unknown registered case")
        obj = plan_case(fixture, case)
    else:
        obj = build_report(fixture)
    rendered = canonical_json(obj)
    if args.check:
        if (HERE / "report.json").read_bytes() != rendered.encode("utf-8"):
            raise ValueError("offline CPython transfer changed")
        print("CPython typed scope, default, and citation replay matched.")
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
