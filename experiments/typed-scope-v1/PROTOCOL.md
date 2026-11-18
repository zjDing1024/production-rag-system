# Typed-scope filtering protocol

Frozen before model calls. Original controlled development study, not a held-out
benchmark, independent semantic verifier or complete retrieval benchmark.

## Scope and trust

The new opt-in module accepts a typed requested scope and typed evidence metadata.
Documentation matches exact kind, project, key and version. Synthetic runtime
matches exact kind, application, key and UTC-second timestamp. Fields are supplied
by the caller, not inferred from natural language, IDs or answer text. The filter
does not read the question or expected value. Source metadata must already be
trusted/correct; it is not authorization, authentication or a truth check. A lying
metadata record or inconsistent natural-language question can pass. The evaluation
fixture's query/scope agreement is an AI-reviewed invariant, not a product ability.

No match returns `not_run/no_matching_scope`, with no model call. This deterministic
block is not model abstention. Model refusal, invalid output and transport failure
are retained as different outcomes. A text answer `None` can be the correct Flask
configuration value; it is not lack of evidence or an instruction to refuse.

## Frozen cases

Four request groups / three fact families: Flask old/new version defaults, invented
application timeout, and invented time-specific health route. Each has EN/ZH, a
sufficient/insufficient same-question pair, and the complete independent 2x2 display
order × arbitrary-ID mapping factorial. Total: 64 rows / 32 paired conditions.
Every row supplies two records of the same kind; no documentation-to-ID-1 shortcut.
Count, fields and text lengths match within each positive/negative pair. Opaque IDs
are resolved as supplied, never assigned by relevance or source kind.

Version positives contain both 1.1.4 (43200 seconds) and 3.1.2 (None); requested
version changes which value/source is correct. Missing requested versions replace
only that record with the existing pinned 3.1.0 documentation. Entity negatives
replace Cedar with Maple while retaining its value. Time negatives replace the
requested 09:00 snapshot with 07:00 while retaining its value. Wrong-scope values
may equal the expected answer, so string presence alone is not support. All runtime
records are original inventions, not user or production telemetry.

The additional official sources were fetched at fixed commits and whole-file SHA
verified before freeze. Only original summaries, URLs, hashes/offsets and source
verification manifest are published, not new upstream source files. Existing
BSD-3-Clause attribution is retained. Offline audits verify the frozen receipt and
existing local corpus, not the remote upstream bytes. New requests are development
targets over known docs; older cases are regression only.

## Intervention and budget

Ungated: both original offered records. Gated: only exact metadata matches, or no-run
if none. Both arms use the exact previously frozen `matched-evidence-v1` branched
answer schema and identical system prompt/options. The application production
`LocalGenerator`, previous gates, old reports and defaults remain unchanged. No LLM
selector is used this round. Context and its allowed citation-ID set change as the
intended intervention; no citation filling, text repair or normalization is used.

Use pinned Qwen3.5-0.8B Q4_0 and official llama.cpp b12359, CPU-only, four threads,
context 4096, one slot, thinking off, temperature 0, seed 42, max 512 output tokens.
Counterbalance arm order in cases.json. No retries or tuning on results. Expect
64 ungated and 32 gated generation calls, plus 32 metadata no-runs. If execution is
partial, preserve actual calls and do not turn missing results into refusals.
Coordinate the live window with the other portfolio job; no speed/memory claim.

## Prespecified outcomes

Keep these layers separate: supplied scope coverage; deterministic filter behavior;
model call/no-run; final Python contract; citation membership; AI-reviewed citation
scope support; exact answer correctness; legitimate model refusal; incorrect answer;
unsupported accepted answer; transport/protocol failures.

Each sufficient row has one fully supporting record. Record both any-scoped-citation
and all-citations-scoped indicators. Strict accepted supported correctness requires
the right value and every citation in scope, not only one good citation mixed with
an irrelevant version/entity/time. Report mixed-scope citations separately from no
supporting citation; this conservative fixture criterion is not a general multi-hop
entailment rule. A value string that happens to match without a scoped citation is
not supported for this question.

Pair success requires a supported correct accepted answer in the positive condition
and either legitimate model refusal or correctly classified metadata no-run in its
negative. Report the latter separately, including counts when no model was asked.
Report both languages jointly, all ID/order layouts, and requested-version switching;
do not count correlated layouts as independent facts. Report row, pair and request-
group denominators even if filtering skips generation. Raw support judgments are
AI annotations, not human calibration or automatically proven entailment.
