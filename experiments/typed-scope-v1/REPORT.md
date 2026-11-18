# Typed scope comparison: measured result

2026-11-19 MYT. Original controlled development experiment, AI-assisted
implementation and review, not a held-out benchmark or production safety claim.
The [frozen protocol](PROTOCOL.md), cases, source summaries, code and model/runtime
hashes were fixed before 96 real CPU generation calls. No retries or result-driven
changes were made to those files. All 64 rows completed; the owned server stopped.

## What changed, and what did not

Both arms receive the same natural-language question. Ungated sends both offered
same-kind records to the prior branched generator. Gated first compares caller-
supplied kind, subject, key and version/time exactly, sends only matching records,
or makes no call if none match. It neither reads expected values nor infers scope
from the question. The prompt, branched answer/refusal schema and sampling settings
are otherwise the same. Both arms validate citations against their actual supplied
ID set; no citations or answer text are repaired.

Filtering changes wrong-scope distractors, context length and the allowed ID set
at once. This is a pipeline strategy comparison, not isolated evidence of improved
model scope reasoning or proof that generic context trimming has the same effect.
There is no LLM selector, no automatic retrieval or default production change.

## Offered coverage and correlated design

64 rows = 4 request groups × 2 languages × 2 evidence conditions × 4 layouts.
The four groups represent **three fact families**: old/new Flask default, invented
application timeout and invented time-specific health route. Within each of the
32 same-question pairs, count, order, fields and character lengths stay matched.
Only the requested version record, entity or time changes. Every row has two
records of the same kind. Order and opaque ID assignment are independently crossed.

32 rows contain exactly one scoped supporting record; 32 lack it. Some missing-
scope rows deliberately contain the same literal value in another version/entity/
time. Literal substring presence alone is therefore not support. `None` is a
valid configuration value, not a missing record or refusal. All synthetic names,
times and values are inventions, not real telemetry.

| Layer | Ungated | Typed gate |
|---|---:|---:|
| Offered rows, positive / negative | 32 / 32 | 32 / 32 |
| Actual generator calls | 64 | 32 |
| Accepted `answered` outputs | 64 | 32 |
| Deterministic `not_run/no_matching_scope` | 0 | 32 |
| Legitimate model refusals | 0 | 0 |
| Invalid response / transport error | 0 / 0 | 0 / 0 |
| Supported correct accepted positive answers | 23 / 32 | 32 / 32 |
| Accepted answers with no scoped citation | 36 | 0 |
| Accepted answers with mixed scoped/unscoped citations | 1 | 0 |
| Accepted wrong values with all citations scoped | 4 | 0 |
| Correct metadata blocks / false metadata blocks | 0 / 0 | 32 / 0 |
| Final success across all offered rows | 23 / 64 | 64 / 64 |
| Both conditions successful | 0 / 32 pairs | 32 / 32 pairs |

The gated 64/64 outcome is **32 model answers plus 32 deterministic no-runs**, not
64 correct answers, 32 model refusals or model understanding of unanswerability.
The filter's perfect metadata match count is guaranteed by this curated exact-
match fixture; the model's 32 positive answers are separately measured, not implied
by a metadata pass. Metadata/text consistency and question/scope agreement were
reviewed before requests, not established by the production filter.

## Answer and citation correctness are separate

Strict value success uses AI-reviewed exact requested values plus **every citation
in scope**. Mixed citations are not accepted as supported just because one is good.
This fixture has one fully supporting record per positive; this is not a generic
multi-source entailment rule.

| Positive group, eight correlated rows each | Ungated correct + scoped | Gated |
|---|---:|---:|
| Flask 1.1.4, 43200 seconds | 8 / 8 | 8 / 8 |
| Flask 3.1.2, literal None | 5 / 8 | 8 / 8 |
| Synthetic Cedar timeout at fixed time, 17 | 8 / 8 | 8 / 8 |
| Synthetic Cedar route at fixed time, /ready-new | 2 / 8 | 8 / 8 |

All 32 ungated negative rows were answered without scoped support. Among its
positive failures, three new-version answers cite the old version and give 43200;
one time answer cites an old snapshot. Another time answer gives `Ready-New`,
which omits `/` and changes case. Four Chinese time answers give timestamps rather
than the requested route; one of those also mixes both source citations.
These nine positive failures are retained unchanged.

**Scoring sensitivity, disclosed after execution:** the frozen protocol specifies
right/exact value but does not require the whole answer string to contain only the
literal. Two English ungated sentences explicitly give the unchanged `/ready-new`
and count as value-correct under AI review. If the entire answer must equal the
expected literal with no prose, ungated is **21/32** and gated remains **32/32**.
This additional exact-string metric is not retroactively called prespecified.
No case/slash/whitespace normalization or repair is used in either judgment.

## Matched and invariance measures

- Requested-version positive switching: both old/new questions correct in **5/8**
  ungated language/layout pairs, **8/8** gated pairs.
- Positive/negative pair success in both languages jointly: **0/16** ungated
  group/layout combinations, **16/16** gated.
- Success across all four layouts and both languages: **0/4** ungated request
  groups, **4/4** gated. These are four groups, not four independent fact families.

The four order/ID repeats and EN/ZH translations are correlated. These counts
show finite-fixture invariance, not population reliability, causal proof of an
ID shortcut, human-calibrated accuracy or an independently held-out evaluation.
Prior date results are unchanged and not re-scored under this new strategy.

## Reproducibility, provenance and remaining limits

[Offline replay](README.md) reconstructs wire requests, callback/no-run decisions,
source-ID resolution, strict Python contracts and all arithmetic from raw records.
It detects changed fixtures, records and self-consistently rehashed altered prompts.
Semantic annotations remain disclosed AI judgments, independently read by another
AI reviewer, not automatic entailment proof or a substitute for human evaluation.

Whole-source official Flask downloads and license hashes were checked before the
freeze. Only original summaries/receipts are published; no new upstream source
files or model binaries are included. Independent pre-run review checked retained
excerpts, not both new whole files. Offline CI does not fetch those remote sources;
`verify_sources.py --fetch` optionally rechecks their pinned whole bytes.

The run used the pinned free local Qwen/llama.cpp CPU setup from [README](README.md).
It completed in one coordinated run with no model/runtime error. Best-effort server
`/proc` RSS/high-water readings and observed durations are preserved in the manifest,
not used as a latency/memory comparison. No native GBNF compiler claim is made.

A false metadata label, contradictory in-scope records or a natural-language query
inconsistent with its typed scope can still pass this filter. Such input is tested
as a trust-boundary limitation. Metadata filtering is not authentication,
authorization, external truth verification, semantic evidence sufficiency, or a
replacement for a caller's correct scope construction.
