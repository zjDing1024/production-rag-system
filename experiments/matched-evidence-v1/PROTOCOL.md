# Matched evidence protocol (frozen before model calls)

This is an AI-authored development experiment, not a held-out benchmark, real
telemetry, retriever evaluation or production default change.

## Design

Four new question families cross documentation / explicitly invented runtime scope
with numeric / nonnumeric answers. Eight bilingual questions each appear verbatim
under sufficient and insufficient evidence: 16 rows, 8 matched pairs. EN/ZH share
facts and are not independent observations.

Every row supplies two ordered records: a source-derived documentation note followed
by an original synthetic snapshot. All records retain the same fields and padding;
span lengths are exactly 227 and 235 characters. Within a documentation pair only
the documentation setting/value changes to a related different setting. Within a
runtime pair only the synthetic subject changes Orchid to Willow. There are no
contradictory values injected as a substitute for missing support. The wrong-subject
snapshot deliberately retains the expected value: string matching cannot establish
entity-bound support. Questions ask effective configuration, not observed URL paths.

Documentation notes join two explicitly anchored fields in the pinned official
Flask 3.1.0 corpus. They are original structured notes, not continuous verbatim
excerpts. Snapshot subjects, date and values are entirely invented, never observed
from a person, account or service. Source/label metadata is excluded from the model
request; only question, numeric span ID and record text are supplied.

## Fixed execution

Use the existing `numbered-spans-v1` selector unchanged with arm `numbered_span`.
Its bounded ID enumeration proves source resolution, not semantic support. Run one
selector per row. On a valid selected span, run both answer arms on the **same**
original selected text. On insufficient or failed selector output, make no generator
calls and preserve that state separately. Do not force a downstream answer from a
failed selection merely to increase a denominator.

The legacy arm is the unchanged `LocalGenerator` request/schema. The branched arm
changes only its JSON schema to whole-object `anyOf` answer/refusal alternatives.
Prompt, user text, token budget and final Python validator remain identical. The
answer branch requires nonempty answer text and at least one offered citation; it
also moves the existing Python 4000-character limit into its schema. The refusal
branch requires empty answer and no citations. No unconditional citation
fill, answer rewriting, whitespace normalization or semantic repair is permitted.
GBNF/runtime capability and Python-only constraints are reported separately; JSON
schema shape validation is not described as native grammar acceptance. The request
interception helper is for this sequential experiment, not a concurrent server.

Pinned Qwen3.5-0.8B Q4_0, official llama.cpp b12359, four CPU threads, context 4096,
one parallel slot, no GPU; temperature 0, seed 42, maximum 512 output tokens, thinking
disabled. Conditions and generator arms are counterbalanced in cases.json. No retry,
parameter tuning or protocol modification after outcomes. Reuse the prior pinned
asset downloader and verify model/runtime SHA before execution. Keep assets outside
Git. Run after the other portfolio worker's timed benchmark to avoid CPU contention.

## Outcomes fixed in advance

1. Offered sufficiency and actual entity/key/time scope, from frozen AI source labels.
2. Selector structure/ID resolution, invalid output and transport failure separately.
3. Selected support for the exact question, not merely containing the answer string.
4. Valid positive selection versus legitimate refusal versus false refusal.
5. Each downstream arm's Python contract validity, citation membership, AI-assessed
   semantic support/correctness, and accepted supported answer/refusal separately.
6. Pairwise selection success requires supporting selection on the sufficient row
   AND a legitimate insufficient decision on its matched negative. Pairwise final
   success additionally requires accepted supported answer on the positive and a
   valid refusal on the negative. Invalid output never counts as refusal.
7. Report unsupported accepts and structural-only changes without calling them a
   semantic improvement. A deterministic evidence-blind baseline has identical
   predictions within each pair; always-sufficient, always-insufficient and
   documentation-only baseline policies each score 8/16 rows and 0/8 complete pairs.
   These are computed baselines, not additional model calls.

Do not infer latency, semantic generalization, user mastery, robust evidence use or
agent readiness from these finite tests. Older cases are offline regressions only.
