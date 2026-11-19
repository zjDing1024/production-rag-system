# Index-owned scope and reviewed-value preflight

This is an optional, runnable integration with the repository's actual BM25 and
local generator adapter. Existing retrieval, generation and scope-filter defaults
are unchanged. It is a bounded read-only prototype, not a production RAG or Agent.

## Stages and trust boundaries

1. An operator loads fixed chunk bytes and an index-owned review catalog. The
   catalog binds to a fingerprint of all chunk fields; each reviewed claim binds
   its normalized value to an exact quoted span and the chunk-text hash.
2. A request supplies only natural-language `query` and typed `scope`. It cannot
   replace records, candidates, values or metadata. The caller still has to ensure
   that the question agrees with the typed scope; this code does not infer that.
3. With `scope_gate=True`, enumerate the **complete exact-scope bucket**, including
   records with no query-token overlap. Review its single values before any scoring,
   requested top-k truncation or context packing. Conflict or unknown stops execution.
4. The bounded `EligibleBM25` wrapper calls the unchanged original BM25 for all
   lexical hits using full-index statistics. It intersects eligible IDs with that
   scored order and only then takes the requested top-k. It does not re-index the
   subset, change scores, avoid full scoring or claim faster retrieval.
5. Pack a ranked prefix within the character budget. If at least one chunk fits,
   call an explicitly supplied generator. No generator configured means an offline
   plan. The production `LocalGenerator` still enforces its existing answer contract.

## Runnable offline example

From the repository root, Python 3.10+ and only the standard library:

```bash
PYTHONPATH=src python -m rag_foundation.scoped_pipeline \
  --chunks experiments/indexed-scope-v1/english-correction/example-index/chunks.jsonl \
  --catalog experiments/indexed-scope-v1/english-correction/example-index/catalog.json \
  --request experiments/indexed-scope-v1/english-correction/example-index/request.json \
  --scope-gate -k 1
```

The example has one ranked snippet and one same-scope contradictory snippet with
zero query-token overlap. It must return `not_run/reviewed_value_conflict`, with
`ranking=null` and no model call. Omitting `--scope-gate` yields an offline plan with
only the lexical hit, demonstrating the visibility failure rather than hiding it.
An explicit `--endpoint http://127.0.0.1:PORT` enables the existing local adapter;
no endpoint means no connection, model download or paid service.

```python
from rag_foundation.scoped_pipeline import ClaimIndex, ScopedGenerationPipeline
from rag_foundation.scope_gate import Scope

index = ClaimIndex.from_files(chunks_path, catalog_path)
pipeline = ScopedGenerationPipeline(index, generator=optional_generator)
result = pipeline.answer(query, Scope.from_dict(request_scope), k=1,
                         scope_gate=True, context_characters=12000, scan_limit=128)
```

## Catalog contract

The operator-owned catalog has `schema_version=1`, boolean `complete`,
`chunks_sha256`, and `entries`. Each entry has `chunk_id`, `scope`, and `claim`.
Scope uses the existing typed contract: exact kind/project/key/version for docs,
or exact kind/entity/key/UTC-second timestamp for runtime. One declared scope and
at most one reviewed single-value claim per chunk is supported. This is **not** a
drop-in catalog for mixed-topic unreviewed documents.

A claim is either JSON `null` (missing or unreviewed), or exactly these fields:
`reviewed=true`, `chunk_text_sha256`, `value_type`, `unit`, `value`, `start_char`,
`end_char`, `quote`. Offsets are half-open decoded-character offsets within the
indexed chunk. The exact hash and quote must match those indexed bytes.

Reviewed types are bounded `integer` (no bool/float coercion), exact nonempty
`string`, and literal `null`. Unit is an exact bounded ASCII label. No unit
conversion, numeric parsing, case folding or slash repair occurs. For example,
`claim=null` is unknown, while a reviewed `value_type="null", value=null` is a
present single value. Different types or units yield `incomparable_claims`, not a
claimed contradiction. Only distinct values of the same type/unit are conflicts.

Hashes and quotes catch stale source bytes. They **do not prove** that a hand-
normalized value means what its quote says, nor authenticate the source or operator.
A deliberately false normalized value can pass and is covered as a limitation in
tests. Catalog completeness and scope assignment are operator assertions; copies
and paraphrases of one source are not independent evidence. Python mapping proxies
and frozen claim objects are construction snapshots, not tamper resistance against
privileged code that can replace object attributes.

## Fail-closed and generation states

| Reason | Behavior |
|---|---|
| `catalog_incomplete` | Missing entry/scope anywhere, or `complete=false`: unknown, no ranking or generation |
| `scope_scan_limit` | Too many same-scope records: unknown, never silently truncate review |
| `missing_reviewed_claim` | Full scope is known but not all claims reviewed: unknown |
| `incomparable_claims` | Different type/unit: unknown |
| `reviewed_value_conflict` | Multiple comparable values: deterministic conflict stop |
| `no_matching_scope` | Complete catalog has no requested scope |
| `no_lexical_candidates` | Reviewed scope agrees, but actual BM25 has no hit |
| `context_budget_exhausted` | Ranked candidates exist, none fit the packing budget |
| `generator_not_requested` | Nonempty context, offline `planned` result |

All deterministic stops are `not_run`, not model refusals. If called, a generator's
`answered`, `evidence_abstained`, `invalid_response` and `transport_error` remain
distinct and unchanged. Semantic support remains `unverified`. A tiny context
budget cannot hide a conflict, because preflight already inspected the full bucket.
Partial packing can omit additional agreeing records after a complete preflight.

The hard index cap is 2,048 chunks / 2,000,000 text characters; each input file is
bounded to 8 MB. The scope review cap defaults to 128 (at most 2,048), generation
k is 1..3 and context budget is 1..12,000 characters. The scope cap bounds claim
review count, not scan CPU work: locating matching IDs still traverses the bounded
whole index. This implementation is correctness-first, not scale/performance work.

## Design references

Lucene's [pinned BooleanWeight construction](https://github.com/apache/lucene/blob/releases/lucene/10.3.1/lucene/core/src/java/org/apache/lucene/search/BooleanWeight.java#L44-L56)
uses non-scoring mode for non-scoring clauses. That separation is a conceptual
reference for eligibility versus relevance, under its
[Apache-2.0 license](https://github.com/apache/lucene/blob/releases/lucene/10.3.1/LICENSE.txt).
Our full-result wrapper and reviewed-value preflight are original and are not
Lucene implementations or semantic verification supplied by Lucene.
The earlier [Qdrant reference](typed-scope-gate.md#design-reference-and-evidence)
informs exact metadata matching only. No third-party implementation was copied.

[Protocol and reproduction](../experiments/indexed-scope-v1/README.md) ·
[Recorded mechanism results](../experiments/indexed-scope-v1/REPORT.md)
