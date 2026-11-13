"""Run three frozen, evidence-conditioned local generation checks, without retrieval."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parent


def sha256(path):
    value = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(4 * 1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def write_json(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "runs/run-001")
    args = parser.parse_args()
    out = args.output.resolve()
    if not out.is_relative_to(ROOT):
        raise ValueError("run output must stay in this experiment directory")
    out.mkdir(parents=True, exist_ok=False)
    cases = json.loads((ROOT / "cases.json").read_text(encoding="utf-8"))
    model_metadata = json.loads((ROOT / "model-download.json").read_text())
    model = ROOT / model_metadata["filename"]
    if sha256(model) != model_metadata["expected_sha256"]:
        raise ValueError("model checksum mismatch")
    binary = ROOT / "runtime/llama-b12359/llama-server"
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    command = [str(binary), "--model", str(model), "--alias", "qwen35-local-smoke",
               "--host", "127.0.0.1", "--port", str(port), "--ctx-size", "2048",
               "--threads", "4", "--threads-batch", "4", "--parallel", "1",
               "--gpu-layers", "0", "--no-agent", "--no-webui", "--no-ui-mcp-proxy",
               "--reasoning", "off", "--chat-template-kwargs", '{"enable_thinking":false}']
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("LLAMA_") and k not in {"HF_TOKEN", "HUGGING_FACE_HUB_TOKEN"}}
    for key, folder in [("HOME", "home"), ("XDG_CACHE_HOME", "cache")]:
        path = ROOT / folder
        path.mkdir(exist_ok=True)
        env[key] = str(path)
    env["HF_HUB_OFFLINE"] = "1"
    manifest = {"scope": cases["scope"], "started_utc": datetime.now(timezone.utc).isoformat(),
                "command": command, "cases_sha256": sha256(ROOT / "cases.json"),
                "runner_sha256": sha256(Path(__file__)), "model": model_metadata,
                "runtime_binary_sha256": sha256(binary), "requests": [],
                "network_scope": "loopback HTTP only during generation; no external model API",
                "generation_mode": "non-thinking, CPU, no tools, no retriever"}
    write_json(out / "manifest.json", manifest)
    process = None
    start = time.monotonic()
    try:
        with (out / "server-stdout.log").open("w") as stdout, (out / "server-stderr.log").open("w") as stderr:
            process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=stdout, stderr=stderr)
            for _ in range(300):
                if process.poll() is not None:
                    raise RuntimeError(f"server exited during startup with {process.returncode}")
                try:
                    with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=1) as r:
                        health = json.load(r)
                    if health.get("status") == "ok":
                        break
                except (OSError, urllib.error.URLError):
                    pass
                time.sleep(0.2)
            else:
                raise TimeoutError("model server did not become ready within startup budget")
            manifest["startup_seconds"] = time.monotonic() - start
            for case in cases["cases"]:
                request = {
                    "model": "qwen35-local-smoke",
                    "messages": [{"role": "system", "content": cases["system_prompt"]},
                                 {"role": "user", "content": f"CONTEXT:\n{case['context']}\n\nQUESTION:\n{case['question']}"}],
                    "temperature": 0, "seed": 42, "max_tokens": 192, "stream": False,
                    "chat_template_kwargs": {"enable_thinking": False},
                }
                write_json(out / f"{case['id']}-request.json", request)
                before = time.monotonic()
                entry = {"id": case["id"], "expected_behavior": case["expected_behavior"]}
                try:
                    req = urllib.request.Request(f"http://127.0.0.1:{port}/v1/chat/completions",
                                                 data=json.dumps(request, ensure_ascii=False).encode(),
                                                 headers={"Content-Type": "application/json"}, method="POST")
                    with urllib.request.urlopen(req, timeout=180) as r:
                        raw = r.read()
                        entry["http_status"] = r.status
                    (out / f"{case['id']}-response.raw.json").write_bytes(raw)
                    result = json.loads(raw)
                    entry.update(content=result["choices"][0]["message"].get("content"),
                                 finish_reason=result["choices"][0].get("finish_reason"),
                                 usage=result.get("usage"), status="generated")
                except Exception as exc:
                    entry.update(status="failed", error=repr(exc))
                entry["elapsed_seconds"] = time.monotonic() - before
                manifest["requests"].append(entry)
                write_json(out / "manifest.json", manifest)
                print(json.dumps(entry, ensure_ascii=False), flush=True)
            try:
                status = Path(f"/proc/{process.pid}/status").read_text()
                manifest["server_memory"] = [line for line in status.splitlines()
                                              if line.startswith(("VmRSS:", "VmHWM:"))]
            except OSError:
                pass
    except Exception as exc:
        manifest["error"] = repr(exc)
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
        manifest["server_returncode_after_cleanup"] = process.returncode if process else None
        manifest["server_stopped"] = process is None or process.poll() is not None
        manifest["finished_utc"] = datetime.now(timezone.utc).isoformat()
        write_json(out / "manifest.json", manifest)
    print(json.dumps({"output": str(out), "server_stopped": manifest["server_stopped"],
                      "error": manifest.get("error")}, ensure_ascii=False), flush=True)
    return 1 if manifest.get("error") or any(q["status"] == "failed" for q in manifest["requests"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
