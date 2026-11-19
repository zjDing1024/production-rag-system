# Frozen offline indexed-scope protocol

The experiment validates deterministic placement and integration, not model quality.
No LLM is required. A recorded generator spy accepts supplied IDs and returns a fixed
sentinel; it does not extract fixture values or demonstrate correct answers. A separate
local HTTP fixture verifies the existing LocalGenerator transport and contract path.
No paid resources, real runtime snapshots, private files or default changes.

## Intervention and ordering

Both arms build the actual project BM25 over identical full chunk corpora. Ungated
uses all lexical candidates. Scoped uses an operator-owned, chunk-fingerprint-bound
catalog, exactly filters typed scope, and checks **every record in that scope** for
reviewed comparable single-value claims before scoring, top-k or context packing.
Missing scope anywhere or an explicitly incomplete catalog is conservatively unknown.
More scope matches than the scan cap is unknown, not truncated success. Missing review
or incomparable type/unit is unknown. More than one distinct comparable value is
conflict. Only a complete agreeing bucket can proceed. No conflict means agreement
within this curated catalog, not full-corpus truth, semantic entailment or security.

Normalization is supplied by the operator review, not inferred from text: integer
(excluding bool, bounded magnitude), exact string, or explicit null; exact unit label.
No string/case/slash repair, numeric coercion, unit conversion or parsing of prose.
A null reviewed value is distinct from a missing claim. Scope/query consistency and
reviewed value meaning are fixture-review assertions; the product cannot prove them.
The request cannot replace chunk metadata, values or candidate records.

The same full-index N, document frequency and lengths feed BM25 in both arms. The wrapper obtains full-index scores/order, intersects eligible IDs, then applies
the requested top-k. It does not avoid full scoring, promise speed, or physically
reorder the original scorer. A filtered corpus is not re-indexed.
No lexical overlap still means no BM25 hit, but it cannot hide a same-scope reviewed
conflict from the earlier complete-bucket scan. Packing is a bounded ranked prefix;
partial packing is allowed only after complete preflight. Budget is not a scope scan.

## Constructed controls and outcomes

The new cases include EN/ZH same-question lexical-zero agreement/conflict pairs,
non-numeric path agreement/conflict, score-tied order/ID swaps, missing review,
incomparable units, unassigned metadata, incomplete catalog, scan cap, packing cap,
no scope match, no lexical match, partial packing, wrong-version distractors,
explicit null, and actual top-1 exclusion rescued by pre-ranking eligibility.
The ID/order repeats are not independent semantic facts or population estimates.

Report all offered cases, scope matches/review coverage, preflight status/reason,
lexical and rank omissions, budget omissions, and actual spy calls separately.
Conflict/unknown/no-match/budget/no-lexical stops are `not_run`, not model refusals.
Preserve transport/protocol errors from injected generators; no retry or repair.
Expected routing labels are outside the request/catalog and never passed to the
pipeline. Assert exact routed outcomes and score invariance, not answer accuracy.

## Bounded interpretation

One declared scope and at most one reviewed value per chunk is required. This is
not a drop-in annotation scheme for arbitrary mixed-topic documents. The catalog
complete flag and all-record scope assignment are operator assertions. Source
hash/quote binding detects stale bytes, not whether a normalized value faithfully
expresses the quoted text. Different types or units are unknown/incomparable, not
classified as conflict. The scope review cap limits claim review count, not index
iteration or CPU time: at most 2048 chunks are traversed. The Python construction
snapshot/mapping proxies are not tamper resistance against code with object access.
Copies or paraphrases from one source do not provide independent evidence.

All catalog quotes are exact spans of the indexed original fixture text. The two
version examples are original factual paraphrases, not verbatim upstream chunks;
their public source/license receipts are referenced from typed-scope-v1. A span
hash binds the review to these fixture bytes, not directly to upstream document
bytes or real observations. No new third-party text is redistributed.
