"""Explicit seven-call PostgreSQL citation comparison, or offline receipt audit."""

import argparse
import hashlib
import http.client
import importlib.util
import json
from pathlib import Path
import re
import socket
import subprocess
import tempfile
import time
from unittest.mock import Mock, patch

from replay import CASES, HERE, ROOT, load_oracle
from rag_foundation.corpus import canonical_json
from rag_foundation.safe_document_agent import _build_index
from rag_foundation.scoped_pipeline import ScopedGenerationPipeline

ASSET_MANIFEST = ROOT / "experiments/local-generation-smoke/sources.json"
RECEIPT = HERE / "recorded-live.json"
LOCK = HERE / "live.lock.json"
FLAGS = (
    "--alias", "local-model", "--host", "127.0.0.1", "--ctx-size", "4096",
    "--threads", "4", "--threads-batch", "4", "--parallel", "1", "--gpu-layers", "0",
    "--no-agent", "--no-webui", "--no-ui-mcp-proxy", "--reasoning", "off",
    "--chat-template-kwargs", '{"enable_thinking":false}',
)
# A deliberately narrow, frozen display-value scorer; not a semantic judge.
ZERO_MS = re.compile(r"0[ \t]*(?:ms|milliseconds?)[.]?", re.IGNORECASE | re.ASCII)


def sha(path):
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def verify_lock():
    lock = json.loads(LOCK.read_bytes())
    if lock["server_flags"] != list(FLAGS):
        raise ValueError("frozen CPU flags changed")
    for path, expected in lock["inputs"].items():
        if sha(ROOT / path) != expected:
            raise ValueError(f"frozen input changed: {path}")
    return sha(LOCK)


def adapter():
    spec = importlib.util.spec_from_file_location(
        "postgres_fixed_adapter", ROOT / "experiments/typed-scope-v1/adapter.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.BranchedGenerator, module.expected_request


def annotation(name, outcome):
    gold = load_oracle()["cases"][name]
    called = outcome["generator_called"]
    generation = outcome["generation"]
    state = outcome["status"]
    row = {
        "outcome": state if called else outcome["reason"],
        "canonical_zero_ms": False,
        "literal_citations": [],
        "truth_of_zero_ms_for_pinned_question": None,
        "cites_requested_setting_default": False,
        "classification": state if called else "deterministic_stop",
    }
    if state == "evidence_abstained" and called:
        row["classification"] = "model_abstention"
    if state != "answered":
        return row
    ids = [item["chunk_id"] for item in outcome["context"]]
    citations = generation["citation_ids"]
    # Format-valid membership is reported separately from reviewed claim attribution.
    if not citations or not set(citations) <= set(ids):
        raise ValueError("accepted response cited outside the frozen context")
    canonical = ZERO_MS.fullmatch(generation["answer"].strip()) is not None
    matching = gold["citation"] is not None and citations == [gold["citation"]["chunk_id"]]
    row.update(canonical_zero_ms=canonical, literal_citations=citations,
               truth_of_zero_ms_for_pinned_question=(name != "pg16-neighbors-only") if canonical else None,
               cites_requested_setting_default=matching,
               classification=("correct_cited_supported" if matching and canonical else
                               "noncanonical_answer" if matching else "unsupported_answer"))
    return row


def execute(client, expected_request, *, offline_wires=None):
    rows = []
    for case_number, (name, (intent, records)) in enumerate(CASES.items()):
        pipeline = ScopedGenerationPipeline(_build_index(records), client)
        row = {"case": name, "arms": {}}
        # Alternate order; two scoped positives and three deterministic stops.
        order = ("unscoped", "scoped") if case_number % 2 == 0 else ("scoped", "unscoped")
        for arm in order:
            client.last_payload = None
            def one_call():
                return pipeline.answer(intent.query, intent.scope, k=1, context_characters=512,
                                       scope_gate=(arm == "scoped"), scan_limit=16)
            if offline_wires is None:
                result = one_call()
            else:
                wire = offline_wires[name][arm]
                connection = Mock()
                if wire["request"] is not None:
                    envelope = wire["result"]["generation"]["raw_response"]
                    transport = wire["result"]["status"] == "transport_error"
                    reason = wire["result"]["reason"]
                    if transport and not reason.startswith("http_"):
                        raise ValueError("offline audit cannot replay uncaptured transport failure")
                    if envelope is None:
                        raise ValueError("offline audit cannot replay uncaptured response")
                    response = Mock()
                    response.status = int(reason.removeprefix("http_")) if transport else 200
                    response.read.return_value = envelope.encode("utf-8")
                    connection.getresponse.return_value = response
                with patch("rag_foundation.generation.http.client.HTTPConnection",
                           return_value=connection) as connection_factory:
                    result = one_call()
                if connection_factory.call_count != int(wire["request"] is not None):
                    raise ValueError("offline wire count changed")
            expected = (expected_request(intent.query, result["context"])
                        if result["generator_called"] else None)
            if expected != client.last_payload:
                raise ValueError("wire request differed from fixed adapter")
            gold_status = load_oracle()["cases"][name]["status"]
            if (arm == "scoped" and gold_status == "stopped"
                    and (result["reason"] != "no_matching_scope" or result["generator_called"]
                         or result["ranking"] is not None or result["context"])):
                raise ValueError("scoped negative did not stop before ranking and generation")
            must_call = arm == "unscoped" or gold_status == "answered"
            if result["generator_called"] is not must_call:
                raise ValueError("model-call budget changed")
            row["arms"][arm] = {"request": client.last_payload, "result": result,
                                "review": annotation(name, result)}
        rows.append(row)
    return rows


def summary(rows):
    counts = {}
    for arm in ("unscoped", "scoped"):
        outcomes = [row["arms"][arm] for row in rows]
        counts[arm] = {"model_calls": sum(o["request"] is not None for o in outcomes)}
        for label in ("correct_cited_supported", "unsupported_answer", "noncanonical_answer",
                      "model_abstention", "deterministic_stop", "transport_error", "invalid_response"):
            counts[arm][label] = sum(o["review"]["classification"] == label for o in outcomes)
    return counts


def ready(process, port):
    until = time.monotonic() + 60
    while time.monotonic() < until:
        if process.poll() is not None:
            raise RuntimeError("fixed CPU server exited before readiness")
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=1)
        try:
            connection.request("GET", "/health")
            response = connection.getresponse()
            if response.status == 200 and json.loads(response.read(1024)).get("status") == "ok":
                return
        except (OSError, ValueError, http.client.HTTPException):
            pass
        finally:
            connection.close()
        time.sleep(0.2)
    raise TimeoutError("fixed CPU server not ready")


def live(assets, locked_sha):
    pins = json.loads(ASSET_MANIFEST.read_bytes())
    model, runtime = pins["model"], pins["runtime"]
    model_path = (assets / model["filename"]).resolve()
    binary = (assets / runtime["server_path"]).resolve()
    if sha(model_path) != model["expected_sha256"] or sha(binary) != runtime["server_sha256"]:
        raise ValueError("model/server checksum mismatch")
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    new_client, expected = adapter()
    with tempfile.TemporaryDirectory(prefix="pg-cpu-scope.") as work:
        with tempfile.TemporaryFile(dir=work) as log:
            process = subprocess.Popen([str(binary), "--model", str(model_path), "--port", str(port), *FLAGS],
                                       cwd=work, env={"HOME": work, "XDG_CACHE_HOME": work,
                                                    "HF_HUB_OFFLINE": "1", "LANG": "C.UTF-8"},
                                       stdout=log, stderr=log)
            try:
                ready(process, port)
                rows = execute(new_client(f"http://127.0.0.1:{port}"), expected)
            finally:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)
    return {"method": "actual-local-cpu", "frozen_sha256": locked_sha,
            "asset_sha256": {"model": model["expected_sha256"], "server": runtime["server_sha256"]},
            "server_returncode": process.returncode, "rows": rows, "summary": summary(rows)}


def check(locked_sha):
    recorded = json.loads(RECEIPT.read_bytes())
    pins = json.loads(ASSET_MANIFEST.read_bytes())
    expected_assets = {"model": pins["model"]["expected_sha256"], "server": pins["runtime"]["server_sha256"]}
    if (recorded["method"] != "actual-local-cpu" or recorded["server_returncode"] != 0
            or recorded["frozen_sha256"] != locked_sha or recorded["asset_sha256"] != expected_assets
            or sha(RECEIPT) != (HERE / "recorded-live.sha256").read_text().strip()):
        raise ValueError("recorded CPU receipt metadata or checksum changed")
    wires = {r["case"]: r["arms"] for r in recorded["rows"]}
    client, expect = adapter()
    rows = execute(client(), expect, offline_wires=wires)
    if rows != recorded["rows"] or summary(rows) != recorded["summary"]:
        raise ValueError("offline receipt differs from exact adapter replay")
    return recorded["summary"]


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    mode = cli.add_mutually_exclusive_group(required=True)
    mode.add_argument("--assets", type=Path, help="explicit pinned local assets; opt in to CPU inference")
    mode.add_argument("--check", action="store_true", help="replay receipt without a model or network")
    mode.add_argument("--plan", action="store_true", help="inspect the fixed top-1 selections offline")
    args = cli.parse_args()
    locked_sha = verify_lock()
    if args.check:
        value = check(locked_sha)
    elif args.plan:
        value = []
        for name, (intent, records) in CASES.items():
            pipe = ScopedGenerationPipeline(_build_index(records))
            value.append({"case": name, "arms": [pipe.answer(intent.query, intent.scope, k=1,
                          context_characters=512, scope_gate=gated, scan_limit=16)
                          for gated in (False, True)]})
    else:
        value = live(args.assets, locked_sha)
    print(canonical_json(value), end="")


if __name__ == "__main__":
    main()
