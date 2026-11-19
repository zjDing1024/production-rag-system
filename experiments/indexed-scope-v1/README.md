# Index-owned scope before top-k, complete reviewed-value preflight

This round closes the previous pre-supplied-record limitation with an optional
actual BM25 → preflight/ranking/packing → generator pipeline. The implementation
and CLI are in [scoped_pipeline.py](../../src/rag_foundation/scoped_pipeline.py),
with [the interface/trust guide](../../docs/indexed-scope-pipeline.md).

The key counterexample has a second same-scope contradiction with **zero lexical
overlap**. Original BM25 cannot return it at any k; a top-1-only evidence check
therefore never sees it. The new complete reviewed-claim bucket stops before
ranking, while the matched agreeing bucket proceeds. This is a deterministic
integration result, not a measured improvement in model answers.

**Input correction retained:** the original English pair unexpectedly shared token
`is`, so it was low-ranked, not zero-overlap. The first invariant check failed;
[that failure](initial-input-check.json) and original frozen bytes remain. A
[separately frozen two-case English supplement](english-correction/PROTOCOL.md)
removes only that accidental token overlap and reproduces the intended mechanism.
Chinese/path controls already were truly zero-overlap. No model or threshold changed.

## Offline reproduction

Python 3.10+, standard library, no network, model, paid API or private data:

```bash
python experiments/indexed-scope-v1/audit_record.py --check
python -m unittest discover -s experiments/indexed-scope-v1 -p 'test_*.py' -v
PYTHONPATH=src python -m unittest discover -s tests -v

# New file required; existing evidence is never overwritten.
python experiments/indexed-scope-v1/run_experiment.py --output build/my-indexed-scope.json
python experiments/indexed-scope-v1/run_correction.py --output build/my-english-correction.json
```

The runner uses real project BM25, catalog preflight and context packing. Its
`RecordingSpy` returns a fixed non-answer sentinel with the supplied first ID;
**it does not infer answers or demonstrate answer support**. The actual production
`LocalGenerator` is exercised by a separate local HTTP contract fixture in tests,
not by an LLM. Real model calls in this study: **zero**. Existing pinned model
experiments remain unchanged; this deterministic mechanism does not justify a
new 586 MB download or recycled model-quality claim.

To inspect an indexed hidden-conflict example without any generator:

```bash
PYTHONPATH=src python -m rag_foundation.scoped_pipeline \
  --chunks experiments/indexed-scope-v1/english-correction/example-index/chunks.jsonl \
  --catalog experiments/indexed-scope-v1/english-correction/example-index/catalog.json \
  --request experiments/indexed-scope-v1/english-correction/example-index/request.json \
  --scope-gate -k 1
```

Expected: `not_run/reviewed_value_conflict`, two scope matches and reviews, no
ranking, no context and no generator call. Omit `--scope-gate` for the unsafe
baseline visibility plan: one lexical record only. Supplying an explicit loopback
`--endpoint` enables the existing generator adapter; the operator must start their
own local model. Default retrieval and generation routes are untouched.

## Evidence and provenance

- [Frozen design](PROTOCOL.md), [cases](cases.json), [content hash lock](freeze.json).
- [Raw original execution](recorded.json), [checksum](recorded.sha256.json).
- [English correction raw](english-correction/recorded.json), [separate lock](english-correction/freeze.json), [counts](english-correction/summary.json).
- [Counts](summary.json), [measured report and limitations](REPORT.md).
- `test_experiment.py` independently replays all routed calls, tampering failures
  and the top-1 counterexample. CI performs offline replay, never a model download.

The source and fixture hashes were frozen before the recorded run. A pre-freeze
AI review found missing textual values in one lexical-ranking fixture; those were
made explicit before freezing. A bounded score check confirmed its intended rank
ordering before execution. This is constructed mechanism development, not blind
semantic evaluation or independent preregistration. All fixture review is AI-assisted.

One scope and one normalized single value per indexed chunk are operator assertions.
A missing catalog entry or scope makes the catalog globally unknown. Missing review,
review-count cap or incomparable type/unit also stops; these are not model refusals.
Quote/hash binding proves byte provenance, not the semantics of the normalized
value. Copies/paraphrases are not independent sources. This bounded implementation
scores the full corpus before intersecting eligibility and taking requested top-k;
it preserves full-corpus statistics, does not avoid scoring or claim speed.

All runtime records are original inventions. Version rows are original factual
paraphrases of [the pinned public Flask documentation receipts](../typed-scope-v1/sources/manifest.json),
not verbatim upstream chunks. Their claim spans bind to those fixture summaries,
not directly to upstream bytes. BSD-3-Clause [attribution](../../NOTICE.md) remains;
no new third-party text or model binaries are distributed. See the guide's pinned
Lucene/Qdrant references for conceptual sources only, with no imported implementation.
