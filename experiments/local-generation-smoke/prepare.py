"""Opt-in pinned public downloads. Python 3.12+, Linux x86_64; no installation."""

import hashlib
import json
from pathlib import Path
import platform
import tarfile
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parent


def verify(path, expected_size, expected_sha256):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(block)
    if path.stat().st_size != expected_size or digest.hexdigest() != expected_sha256:
        raise ValueError(f"size or SHA-256 mismatch: {path.name}")


def acquire(spec):
    destination = ROOT / spec["filename"]
    if not destination.is_file():
        with tempfile.TemporaryDirectory(prefix=".download-", dir=ROOT) as folder:
            temporary = Path(folder) / "artifact"
            with urllib.request.urlopen(spec["url"], timeout=120) as response:
                with temporary.open("wb") as target:
                    while block := response.read(4 * 1024 * 1024):
                        target.write(block)
            verify(temporary, spec["expected_bytes"], spec["expected_sha256"])
            temporary.replace(destination)
    verify(destination, spec["expected_bytes"], spec["expected_sha256"])
    return destination


def main():
    if platform.system() != "Linux" or platform.machine() not in {"x86_64", "AMD64"}:
        raise SystemExit("This pinned runtime is for Linux x86_64 only; no alternate downloads are attempted.")
    sources = json.loads((ROOT / "sources.json").read_text())
    model = sources["model"]
    acquire(model)
    runtime = sources["runtime"]
    archive = acquire(runtime)
    server = ROOT / runtime["server_path"]
    if not server.exists():
        with tarfile.open(archive) as package:
            package.extractall(ROOT / "runtime", filter="data")
    if hashlib.sha256(server.read_bytes()).hexdigest() != runtime["server_sha256"]:
        raise ValueError("llama-server checksum mismatch")
    (ROOT / "model-download.json").write_text(json.dumps(model, indent=2) + "\n")
    print("Verified pinned model and runtime. No program or model was executed.")


if __name__ == "__main__":
    main()
