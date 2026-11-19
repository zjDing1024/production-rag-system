# Actual indexed retrieval and complete reviewed-value preflight

2026-11-20 MYT. Original, AI-assisted bounded integration work, not semantic
benchmarking, model-quality evidence or independent preregistration. Existing
retrieval/generation source files, defaults and historical records are unchanged.

## Result and an input error that remains visible

The original 22 constructed cases completed 44 real pipeline arms. All **22/22
routing outcomes** matched their prespecified expectations. The pipeline uses the
actual project BM25, not a mocked retriever. Generation uses a disclosed fixed
sentinel spy, so **real model calls and answer-accuracy measurements are zero**.

The first experiment test run was **8 passed, 1 failed**: the original English
hidden sentence and question both contain token `is`. Its alleged zero-overlap
label was wrong, although its lower-ranked omission at k=1 and routing result
were real. Pre-run AI review also missed that token. This is an input-design
error, not evidence of BM25 malfunction. [The failure record](initial-input-check.json),
original protocol, frozen fixtures and raw outputs remain unchanged.

Chinese and path pairs already have zero token overlap. A separate English
supplement changes only `The configured duration is ...` to `Configured duration:
...`, retaining question/scopes/values/IDs/options. Independent token/BM25 checks
confirmed zero overlap and only h7 returned before a new freeze and execution.
It then completed **2/2 expected routes** with the unchanged pipeline. Final tests
assert the original discrepancy, corrected invariant and both unmodified records;
they do not silently weaken the original zero-overlap claim into a pass.

## Original 22-case routing layers

| Layer | Ungated | Scoped |
|---|---:|---:|
| Offered constructed cases | 22 | 22 |
| Generator spy callbacks | 20 | 7 |
| Real model calls | 0 | 0 |
| Reviewed single-value conflict, no run | 0 | 7 |
| Incomplete catalog / missing scope, no run | 0 | 2 |
| Missing reviewed claim, no run | 0 | 1 |
| Incomparable type/unit, no run | 0 | 1 |
| Review-count cap exceeded, no run | 0 | 1 |
| No matching scope, no run | 0 | 1 |
| No lexical BM25 hit, no run | 1 | 1 |
| No ranked record fits packing budget, no run | 1 | 1 |

Scoped `status=answered` appears seven times only because the fixture spy returns
a valid sentinel and supplied ID. It is **not seven supported answers**. The
fifteen scoped `not_run` outcomes are not model refusals. The thirteen newly
blocked callbacks comprise seven conflicts, five unknowns and one no-match.
The common budget/no-lexical stops are not attributed to the new preflight.

The two-case corrected English supplement is reported separately: ungated made
two spy callbacks; scoped made one agreement callback and one conflict stop.
These related repaired rows do not add independent semantic facts or expand the
original 22-case acceptance denominator.

## What is actually demonstrated

### 1. Conflict outside ranked evidence

For Chinese numeric and path-string pairs, and the corrected English numeric
pair, BM25 returns only h7 even when asked for the complete two-record index:
z2 has zero overlapping tokens. At k=1, agreement and conflict have byte-identical
baseline packed contexts and scores. Only the hidden reviewed value differs.
The ungated pipeline calls its spy in both conditions. The scoped pipeline reads
both catalog claims before scoring: agreement proceeds, conflict makes no call.
The original English pair demonstrates the weaker low-rank variant, not zero overlap.

Four independent order × opaque-ID assignments of score-tied conflicting snippets
all stop before ranking. They are correlated mechanism controls, not independent
sources or evidence of general natural-language contradiction detection.

### 2. Eligibility must precede the requested top-k truncation

The constructed eligibility case has three wrong-scope lexical leaders and one
lower-ranked eligible record. Original full-index scores are:

| ID | Score | Requested scope? |
|---|---:|---|
| x3 | 0.5371320406085263 | No |
| x2 | 0.50110489154332 | No |
| x1 | 0.4171634630106828 | No |
| ok | 0.2233184842747405 | Yes |

Filtering after original top-1 leaves nothing. Intersecting the complete scored
order with the index-owned scope first returns `ok` at requested k=1. Its score
is unchanged. The original 22 cases contain **27 exact eligible-score comparisons
across 20 nonempty cases**; two cases have no eligible lexical score to compare.
All agree bit-for-bit with the original BM25 on the same complete corpus. A unit
test separately shows a rebuilt subset index would change the score, while this
wrapper preserves N, document frequencies, lengths and average length.

This bounded wrapper intentionally scores the whole corpus before intersection.
It neither physically reorders the existing scorer nor claims less computation,
faster search or production-scale performance. The complete conflict/unknown
preflight itself runs before any scoring, verified by a ranking spy that raises
if called for a conflicting bucket.

### 3. Coverage, unknown, budget and generation remain separate

The wrong-version control excludes the other version before requested top-k.
A reviewed literal null is present evidence, distinct from an absent review.
Missing scope anywhere or a false completeness assertion produces unknown rather
than silently ignoring a possibly relevant record. Missing review, incomparable
units/types and excess review count also fail closed. No-match requires a fully
assigned complete catalog. A complete agreeing bucket can still have no lexical
hit or exceed the packing budget; those reasons are not conflated with conflict.
Partial packing proceeds only after all same-scope claims have been reviewed.

The scan cap bounds reviewed bucket size, not CPU work; the implementation still
traverses at most 2,048 index chunks. Quote/hash bindings and construction-time
snapshots reject stale bytes and malformed input, not malicious in-process object
replacement or false operator declarations.

## Verification and limits

- 136 core tests: previous 110 plus 26 integration/metadata/score/CLI/HTTP tests.
- 58 historical experiment tests and old retrieval/generation audits unchanged.
- 12 final new experiment tests: original/corrected input invariants, matched
  packed contexts, score/route accounting, tampered records, exact replay and CLI.
- **206 total tests passed on the final local state.** The earlier 8/9 invariant
  failure is retained, not counted as a successful first run.
- A real local HTTP test exercises `LocalGenerator` transport and supplied-ID
  validation against a labeled fixture response, not an LLM. All four generator
  outcome classes are preserved in separate mechanism tests.
- CI adds only offline tests/replay to the existing Python 3.11/3.12 matrix.

This catalog supports one declared scope and one reviewed normalized value per
chunk, not arbitrary mixed-topic documents or multi-valued knowledge. The operator
must supply correct completeness, scope and value semantics. Exact spans/hashes
cannot prove the normalized value is entailed by prose. Different type/unit means
unknown, not inferred unit conversion or contradiction. Copies/paraphrases from
one source are not independent evidence. Natural-query/scope consistency, access
permissions, external truth and semantic support remain unverified.

Synthetic records are explicitly invented. Flask version values are original
paraphrases of the previously pinned official BSD-3-Clause sources; no new upstream
text or binary is included. The [guide](../../docs/indexed-scope-pipeline.md)
links verified Lucene/Qdrant conceptual sources and their licenses without importing
implementation. This result does not replace or improve the recorded Nov19 model
experiment by assertion, and does not establish production RAG or Agent readiness.
