# Typed scope: version, entity and exact time

An original opt-in metadata-filter experiment. It asks what happens when callers
already supply trustworthy typed scope, not whether a small model can infer scope.
All runtime examples are invented; no user or real application telemetry is used.

**Recorded result:** ungated produced 23/32 supported correct positive answers and
answered all 32 unsupported rows. Gated produced 32/32 supported correct positive
answers and **did not run the model** on 32 metadata misses. Neither arm produced
a model refusal. See [the layered report](REPORT.md), including stricter whole-answer
literal equality (21/32 vs 32/32) and the small, correlated development-set limits.
No production default was changed.

## 1. Audit without downloading or executing a model

From the repository root:

```bash
python experiments/typed-scope-v1/audit_record.py --check
python -m unittest discover -s experiments/typed-scope-v1 -p 'test_*.py' -v
PYTHONPATH=src python -m unittest discover -s tests -v
PYTHONPATH=src python -m rag_foundation.scope_gate \
  experiments/typed-scope-v1/example-input.json --gate
```

The audit verifies frozen code/fixtures, original request/result hashes, source-ID
mapping, no-run callback counts, exact wire payloads, Python contract replay and
summary arithmetic. It reads disclosed [AI semantic annotations](assistant-review.json);
it does not automatically prove those judgments or rerun model inference. The 14
new experiment tests include tampered fixture/record/wire-request failures and
network-free verification. The core suite has 110 tests, including 15 scope tests.
CI runs offline tests/audits on Python 3.11 and 3.12, not a model download.

[API and trust boundary](../../docs/typed-scope-gate.md) ·
[Frozen protocol](PROTOCOL.md) · [Fixture](cases.json) · [Lock](cases.lock.json) ·
[Preflight call accounting](preflight.json) · [Summary/rows](summary.json) ·
[Raw results](recorded/) · [Archive checksums](recorded-files.sha256.json)

## 2. Optional bounded real CPU reproduction

Linux x86_64, Python 3.12; roughly 586 MB of public downloads and at least 5 GB
available RAM recommended. No paid endpoint, API key, GPU or private data. Assets
stay in a temporary checkout-external directory and are never committed.

```bash
python experiments/evidence-sufficiency-v1/prepare_assets.py --directory /tmp/rag-local-assets
python experiments/typed-scope-v1/run_experiment.py \
  --assets /tmp/rag-local-assets --output build/my-typed-scope-run
```

Always use a new output directory. The runner verifies frozen inputs and binary
hashes, starts one loopback-only CPU server, preserves each completed result, and
stops its server even on error. Budget: 64 offered rows, 64 ungated + 32 gated
calls = 96 calls; 32 deterministic metadata stops have no request. There are no
retries or post-output protocol tuning. One thread-coordination slot avoids the
other portfolio job's measurement window; no timing comparison is claimed.

Pinned [sources and licenses](../local-generation-smoke/sources.json):
Qwen3.5-0.8B-Q4_0 GGUF, revision `004fd086eccea9f7cf867aa07ba328773beef81d`
(Apache-2.0), model SHA-256
`57d1997790d1744fba5b40a7317df71ea5e2acee28c47e78f0cce39c0703f8cf`;
official llama.cpp b12359 (MIT), server SHA-256
`cf07a7d6b6d2c61064105cc0a81360cb5830aacd3d1a949b80eaea3a96fa409f`.
Both arms use the prior branched generator unchanged: temperature 0, seed 42,
max output 512 tokens, thinking off, context 4096, four CPU threads, one slot.
Context text and allowed citation IDs change by filtering; prompt/schema/options
do not otherwise change. Cross-machine output identity is not guaranteed.

The production CLI with `--endpoint` still uses its existing generator contract.
The optional experimental runner explicitly injects the prior branched adapter,
so these live results are not a test of that production CLI's old output shape.

## Sources and freeze integrity

Original summaries of Flask's versioned `SEND_FILE_MAX_AGE_DEFAULT` are backed by
[fixed upstream references and byte hashes](sources/manifest.json). 1.1.4 documents
12 hours (43200 seconds); 3.1.2 documents literal `None`. Existing 3.1.0 is a
wrong-version distractor, even though it also documents `None`. The source docs
are BSD-3-Clause; [attribution](../../NOTICE.md) is preserved. New upstream source
files are not included, only original summaries and verification receipts.

The author checked whole downloaded source and license bytes before freezing.
The independent pre-run AI reviewer checked retained short excerpts and the
existing 3.1.0 corpus, not the new whole-source bytes. Offline audit verifies the
receipt and existing corpus only. An optional public-network recheck is explicit:

```bash
python experiments/typed-scope-v1/verify_sources.py          # no network
python experiments/typed-scope-v1/verify_sources.py --fetch  # fetch pinned official docs/license
```

Freeze integrity is recorded by content hashes in `cases.lock.json`, created before
the first model request. Local freeze commit `72c4f627ef0847d6e9a9a049f6c8d838a0bb5489`
was an internal chronology aid, not independent preregistration or necessarily a
public commit. The publishing workflow may squash commits; use the file hashes.
