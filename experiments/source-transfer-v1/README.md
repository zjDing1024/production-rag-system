# Two-new-source indexed generation pilot

Actual BM25 → index-owned scope preflight → top-1 → local Qwen generation over
original CPython and Express source summaries. **This is new-source development
evidence, not a blind held-out benchmark or a production reliability claim.**
No production code/defaults or historical experiments were changed.

Recorded result: supported correct positive answers **9/10 ungated → 10/10 scoped**.
The one improvement comes from rescuing a supporting snippet before requested top-1,
not stronger reasoning over the same evidence. Ungated accepts all 12 unsupported
negative answer branches; scoped makes **12 deterministic no-matching-scope stops**,
not model refusals. All 32 real CPU requests finish with valid answer contracts;
there are no valid model abstentions, transport failures or invalid responses.

[Layered report](REPORT.md) · [Summary and every row](summary.json) ·
[AI truth/support annotations](assistant-review.json) · [Frozen rubric](PROTOCOL.md)

## Review without a model or network

Python 3.10+, standard library, from the repository root:

```bash
python experiments/source-transfer-v1/audit_record.py --check
python -m unittest discover -s experiments/source-transfer-v1 -p 'test_*.py' -v
```

The audit verifies source/fixture/code locks, actual BM25 preflight, exact wire
requests, raw result hashes, Python contract replay, no-run calls and arithmetic.
It reads explicit AI semantic annotations, not an automatic truth/entailment oracle.
18 new tests cover input/routing/False-vs-zero boundaries, tampering, no-run credit,
missing citations/support and offline operation. CI performs these offline checks;
it does not download or run a model.

- [Cases and per-case gold/rubric](cases.json), [freeze](cases.lock.json).
- [Actual pre-generation lexical/scoped coverage](preflight.json).
- [Original raw envelopes and requests](recorded/), [checksums](recorded.sha256.json).
- [Pinned public source/license receipts](source-manifest.json).

## Optional bounded CPU reproduction

Linux x86_64, Python 3.12, roughly 586 MB of public downloads and at least 5 GB of
available RAM recommended. No paid service, API key, GPU or private documents.
All model/runtime binaries remain in a temporary directory outside Git.

```bash
python experiments/evidence-sufficiency-v1/prepare_assets.py --directory /tmp/rag-local-assets
python experiments/source-transfer-v1/run_experiment.py \
  --assets /tmp/rag-local-assets --output build/my-source-transfer-run
```

Use a fresh output directory. The runner verifies frozen inputs and binary pins,
starts one loopback server, saves results incrementally and stops its own server
on completion/error. No retries or output-driven tuning. Budget is 22 ungated +
10 scoped calls; the other 12 scoped cases make no request. Both arms use the
same prior branched experimental generator, not a new production output default.

[Fixed model/runtime sources and licenses](../local-generation-smoke/sources.json):
Qwen3.5-0.8B Q4_0 at revision `004fd086eccea9f7cf867aa07ba328773beef81d` (Apache-2.0),
SHA-256 `57d1997790d1744fba5b40a7317df71ea5e2acee28c47e78f0cce39c0703f8cf`;
official llama.cpp b12359 (MIT), server SHA-256
`cf07a7d6b6d2c61064105cc0a81360cb5830aacd3d1a949b80eaea3a96fa409f`.
Temperature 0, seed 42, max output 512 tokens, context 4096, four CPU threads,
one slot, thinking off. Other portfolio measurements were kept out of this live
window. Durations/RSS are observations, not speed/memory comparisons or guarantees.

## What the source oracle means

The source summaries are original, short, manually normalized statements. Full
pinned upstream source and tests were inspected separately and never placed in
retrieval context. The oracle is the same upstream source family, not multiple
independent gold standards. CPython constructor values were checked by parsing
source AST only; neither CPython 3.14 behavior nor Express tests were executed.

CPython 3.13.0 and 3.14.0 use the pinned PSF-2.0 source/license references in the
manifest. Express 4.21.2 and 5.1.0 use pinned MIT sources. Only provenance receipts
and original summaries are published; no new upstream source/test files are copied.
Each chunk's `authored-summary://` reference/hash names the authored summary,
while `source_refs` maps it to the exact upstream hash and line references. Neither
field silently claims that the summary is a verbatim upstream source span.

Optional source rechecking is explicit and independent of model execution:

```bash
python experiments/source-transfer-v1/verify_sources.py          # receipts only, no network
python experiments/source-transfer-v1/verify_sources.py --fetch \
  --directory /tmp/rag-source-oracles                           # pinned public bytes + AST checks
```

`False`, `True`, `absent` and the Express enums are **canonical strings** in the
existing claim schema. This does not add native Boolean support. False is never
coerced to zero or absence. `.default`, `.explicit_example` and `.parameter_presence`
are different production scope keys, not only labels in the report. The complete
catalog and question/scope agreement remain trusted operator assertions.

The local pre-run freeze was commit `575791d384988c24936c3830ded73716fdf09982`.
Use content hashes for provenance; this is not independent public preregistration,
and the final publishing workflow can retain or squash local commits.
