"""Explicit scoped-only CPython CPU pilot; offline --check uses captured envelopes."""
import argparse
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
from unittest.mock import Mock, patch

from audit import HERE, ROOT, ProvenancePipeline, Scope, canonical_json, grade_answer, index_for, load_fixture

sys.path.insert(0, str(ROOT / "experiments/postgres-agent-transfer-v1"))
from compare_live import ASSET_MANIFEST, FLAGS, adapter, ready, sha

FORMAT_SUFFIX = " Give only a bare integer followed by the word seconds, without a period."
RECORD = HERE / "recorded-live.json"
LOCK = HERE / "live.lock.json"


class FixedFormatAdapter:
    def __init__(self, client):
        self.client = client

    def generate(self, query, context):
        return self.client.generate(query + FORMAT_SUFFIX, context)


def verify_lock():
    inputs = json.loads(LOCK.read_bytes())
    if inputs["server_flags"] != list(FLAGS):
        raise ValueError("frozen server flags changed")
    if any(sha(ROOT / path) != expected for path, expected in inputs["inputs"].items()):
        raise ValueError("frozen code or inputs changed")
    return sha(LOCK)


def run(client, expected_request, *, receipt=None):
    rows = []
    for case in load_fixture()["cases"]:
        idx = index_for(load_fixture(), case)
        pipe = ProvenancePipeline(idx, FixedFormatAdapter(client))
        scope = Scope.from_dict(case["scope"])

        def scoped_result():
            return pipe.answer(case["query"], scope, k=1, scope_gate=True)

        client.last_payload = None
        if receipt is None:
            outcome = scoped_result()
        else:
            previous = receipt[case["id"]]
            conn = Mock()
            if previous["request"] is not None:
                generation = previous["outcome"]["generation"]
                response = Mock(status=200)
                if generation["status"] == "transport_error":
                    reason = generation["reason"]
                    if not reason.startswith("http_"):
                        raise ValueError("unrecorded transport failure cannot be replayed")
                    response.status = int(reason[5:])
                if generation["raw_response"] is None:
                    raise ValueError("missing raw envelope")
                response.read.return_value = generation["raw_response"].encode("utf-8")
                conn.getresponse.return_value = response
            with patch("rag_foundation.generation.http.client.HTTPConnection", return_value=conn) as wire:
                outcome = scoped_result()
            if wire.call_count != int(previous["request"] is not None):
                raise ValueError("wire call count changed")
        admitted = case["expected_status"] == "planned"
        if outcome["generator_called"] is not admitted:
            raise ValueError("frozen model-call count changed")
        if not admitted and (outcome["reason"] != "no_matching_scope" or outcome["ranking"] is not None):
            raise ValueError("unsupported case was not stopped before ranking")
        expected = expected_request(case["query"] + FORMAT_SUFFIX, outcome["context"]) if admitted else None
        if expected != client.last_payload:
            raise ValueError("CPU wire payload changed")
        grade = grade_answer(case, outcome["generation"]["answer"], outcome["citations"]) if outcome["status"] == "answered" else None
        rows.append({"case": case["id"], "request": client.last_payload, "outcome": outcome, "grade": grade})
    return rows


def result(rows):
    return {"model_calls": sum(r["request"] is not None for r in rows),
            "deterministic_stops": sum(r["outcome"]["reason"] == "no_matching_scope" for r in rows),
            "exact_verified": sum(bool(r["grade"] and r["grade"]["verified_exact"]) for r in rows),
            "model_abstentions": sum(r["outcome"]["reason"] == "model_abstention" for r in rows),
            "transport_errors": sum(r["outcome"]["status"] == "transport_error" for r in rows),
            "invalid_responses": sum(r["outcome"]["status"] == "invalid_response" for r in rows),
            "answer_branches": sum(r["outcome"]["status"] == "answered" for r in rows)}


def live(assets, freeze):
    manifest = json.loads(ASSET_MANIFEST.read_bytes())
    model_info, runtime = manifest["model"], manifest["runtime"]
    model = (assets / model_info["filename"]).resolve()
    server = (assets / runtime["server_path"]).resolve()
    hashes = {"model": sha(model), "server": sha(server)}
    if hashes != {"model": model_info["expected_sha256"], "server": runtime["server_sha256"]}:
        raise ValueError("wrong model or server checksum")
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    client, expected = adapter()
    with tempfile.TemporaryDirectory(prefix="cpython-cpu-pilot.") as d:
        with tempfile.TemporaryFile(dir=d) as log:
            process = subprocess.Popen(
                [str(server), "--model", str(model), "--port", str(port), *FLAGS], cwd=d,
                env={"HOME": d, "XDG_CACHE_HOME": d, "HF_HUB_OFFLINE": "1", "LANG": "C.UTF-8"},
                stdout=log, stderr=log)
            try:
                ready(process, port)
                rows = run(client(f"http://127.0.0.1:{port}"), expected)
            finally:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)
    if process.returncode != 0:
        raise RuntimeError("CPU server did not shut down cleanly")
    return {"method": "scoped-only-real-cpu", "freeze_sha256": freeze, "assets": hashes,
            "server_returncode": process.returncode, "rows": rows, "summary": result(rows)}


def check(freeze):
    previous = json.loads(RECORD.read_bytes())
    manifest = json.loads(ASSET_MANIFEST.read_bytes())
    if (previous["method"] != "scoped-only-real-cpu" or previous["server_returncode"] != 0
            or previous["freeze_sha256"] != freeze
            or previous["assets"] != {"model": manifest["model"]["expected_sha256"],
                                      "server": manifest["runtime"]["server_sha256"]}
            or sha(RECORD) != (HERE / "recorded-live.sha256").read_text().strip()):
        raise ValueError("receipt metadata mismatch")
    client, expected = adapter()
    rows = run(client(), expected, receipt={r["case"]: r for r in previous["rows"]})
    if rows != previous["rows"] or result(rows) != previous["summary"]:
        raise ValueError("offline receipt does not match captured outputs")
    return result(rows)


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    arm = cli.add_mutually_exclusive_group(required=True)
    arm.add_argument("--assets", type=Path)
    arm.add_argument("--check", action="store_true")
    args = cli.parse_args()
    freeze = verify_lock()
    print(canonical_json(check(freeze) if args.check else live(args.assets, freeze)), end="")


if __name__ == "__main__":
    main()
