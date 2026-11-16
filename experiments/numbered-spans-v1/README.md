# Bounded span selection: copying versus IDs

**Nov 17 MYT development experiment, not a production feature or retrieval benchmark.**
The two selectors receive the identical ordered six-span pool. One copies a whole
span; the other returns its number and the program resolves the original text.
This removes a copying burden, not the requirement to select evidence that answers
the actual question. Neither arm produced an accepted, supported correct answer in
this run. [Results and limitations](REPORT.md).

## Review without a model or network

From the repository root, Python 3.10+ and standard library only:

```bash
mkdir -p build
python -m unittest discover -s experiments/numbered-spans-v1 -p 'test_*.py' -v
python experiments/numbered-spans-v1/audit_record.py > build/numbered-spans-v1-summary.json
cmp experiments/numbered-spans-v1/summary.json build/numbered-spans-v1-summary.json
```

The audit checks source spans/offsets, frozen code and input hashes, complete run
order, raw/request hashes, exact reconstructed prompts, selector/generator contract
replay, routing and original-text materialization. It recomputes counts using the
disclosed [AI semantic annotations](assistant-review.json); it does **not** prove
semantic truth. Labels were authored by one AI assistant and source/label/mechanism
checks performed by a second AI assistant before calls. A second AI assistant also
checked the outcomes. No human or independent external evaluator is claimed.

## Explicit optional live reproduction

Linux x86_64, Python 3.12 used here; approximately 586 MB public asset download and
at least 5 GB available RAM recommended. The existing downloader retrieves pinned
official llama.cpp and the public Qwen GGUF, verifies hashes, and extracts locally.
No API key, paid service, private document, GPU or online inference is used.

```bash
python3 experiments/evidence-sufficiency-v1/prepare_assets.py --directory /tmp/rag-local-assets
python3 experiments/numbered-spans-v1/run_experiment.py \
  --assets /tmp/rag-local-assets --output build/my-span-comparison
```

Use a **new** output directory under `build/` each time. The runner starts and stops
the model server inside the same process environment, listening only on loopback.
It verifies [cases.lock.json](cases.lock.json), source, runtime and model hashes
before requests. It never uploads or commits output. Only the explicitly invoked
downloader needs network access. CPU execution and offline CI do not download models.
Memory telemetry is best-effort and cannot discard completed results if unavailable.

The local run used a temporary checkout-external asset directory; that directory and all server
logs, caches, model weights and third-party binaries are excluded from publication.
Only UTF-8 JSON, original code/tests and documentation are tracked.

## Protocol and provenance

- [cases.json](cases.json): 4 new fact families × answerable/related-unanswerable ×
  English/Chinese = 16 questions. Numeric and nonnumeric facts are balanced in both
  labels. Bilingual versions share facts, so this is not 16 independent facts.
- All questions see the same six source-order spans from the existing pinned Flask
  corpus, 1,877 total characters; maximum span length 466. Gold/source metadata is
  **not sent** to the model. The model sees only `question`, `span_id` and `text`.
- At most one complete span can be selected. Every answerable question has a single
  sufficient span. Both arms may return `sufficient=false, selections=[]`.
- Both schemas enumerate exactly the same permitted IDs. Valid ID output therefore
  does not measure unconstrained ID generation. Prompt output instructions and JSON
  schemas differ by arm: this is an interface-strategy comparison, not a pure
  grammar-only or semantic-capacity ablation.
- Same local Qwen3.5-0.8B Q4_0 and llama.cpp as prior runs: [exact pinned URLs,
  revisions and SHA-256](../local-generation-smoke/sources.json), [license notices](../local-generation-smoke/licenses).
  Model SHA-256 `57d1997790d1744fba5b40a7317df71ea5e2acee28c47e78f0cce39c0703f8cf`;
  server SHA-256 `cf07a7d6b6d2c61064105cc0a81360cb5830aacd3d1a949b80eaea3a96fa409f`.
- Each selector: temperature 0, seed 42, max 512 tokens, thinking disabled. Server:
  context 4096, four CPU threads, one parallel slot, zero GPU layers. No retry or
  outcome-based prompt/validator changes. Counterbalanced arm order is frozen.
- Only a valid positive selection calls the unchanged repository
  [`LocalGenerator`](../../src/rag_foundation/generation.py), with the deterministically
  resolved original span as its only context. Same generator settings and contract
  in both arms. The selector and generator share a model, not independent judges.
- Fixtures/mechanics were locally frozen before inference in development commit
  `3c6958805ac5d30dc96b0306f4c9d0b0798cf7a9`. This is local provenance, not a claim
  that that interim commit is publicly addressable or externally preregistered.
  The [lock](cases.lock.json) and recorded manifest preserve verifiable content hashes
  even if publication squashes local commits. Base was `2bd1a005d39a9141d94b0132481394f1c1998c09`.

## Artifact map

- [mechanics.py](mechanics.py): bounded selector protocol and exact resolution.
- [run_experiment.py](run_experiment.py): explicit pinned local execution and cleanup.
- [recorded/manifest.json](recorded/manifest.json): chronology, parameters, hashes,
  call mapping, telemetry and cleanup status; 32 selector requests and results.
- [recorded-files.sha256.json](recorded-files.sha256.json): compact archive checksum index.
- [assistant-review.json](assistant-review.json): all 32 outcome judgments and reasons.
- [summary.json](summary.json): replayed primary metrics and per-case layers.
- [quote-diagnostics.json](quote-diagnostics.json): clearly post-hoc exact-copy failure
  description; not a relaxed-contract rerun or corrected primary score.

Historical experiments remain unchanged and run only as regression checks. These
are fresh authored targets over a known corpus, not source-document holdout. The
short complete-span quote contract is **different** from the prior free-substring
quote gate, so cross-date quality or speed comparisons are unsupported. Default
retrieval and optional generation APIs are unchanged.
