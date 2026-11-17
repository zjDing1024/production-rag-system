# Nov 18: matched evidence exposes entity and scope failures

The new answer/refusal schema made all 14 attempted generation outputs pass the
existing Python contract. It did **not** make the model reliably use the right
evidence. Seven answers were supported and correct, six were unsupported for the
question, and one changed the requested configuration string. Do not enable this
experiment as a default merely because its output is well-formed.

## Same question, different evidence

The preceding experiment correlated documentation questions with answerability and
runtime questions with missing evidence. This fixture breaks that correlation:

- Documentation asks the same default-value question with either the requested
  official-source note or a related note for a different key.
- Runtime asks the same question about an **invented** app Orchid at an invented
  timestamp, with either its matching snapshot or an otherwise identical snapshot
  for Willow. Both retain general documentation as a distractor.

The wrong-entity snapshot deliberately contains the same value string as the
positive condition. Finding `7` or `/orchid` is not enough to establish Orchid's
configuration. None of these snapshots is real telemetry. Documentation records
are explicitly source-derived structured notes, with original-text anchors, not
pretended continuous quotations. The two records retain count, order, fields and
character lengths within every pair (227 and 235); equal token counts are not claimed.

Four question families × two languages × two conditions = 16 rows, 8 matched pairs.
Both scopes have numeric and nonnumeric positives and negatives. English/Chinese
versions share facts. The corpus is known and terms appeared in old context windows;
the acceptance questions are new targets, not document-holdout generalization.
AI assistants authored/reviewed the labels before execution and cross-checked
outcomes afterward. There was no human annotation, training or outcome-based tuning.

## Selection before generation

All 16 selector responses passed the frozen numbered-span contract:

| Selection layer | Documentation | Synthetic runtime | Total |
|---|---:|---:|---:|
| Offered sufficient / insufficient | 4 / 4 | 4 / 4 | 8 / 8 |
| Supporting selection | 4/4 positives | 4/4 positives | 8/8 positives |
| Insufficient evidence incorrectly selected | 2/4 negatives | 4/4 negatives | 6/8 negatives |
| Legitimate refusal | 2/4 negatives | 0/4 negatives | 2/8 negatives |
| False refusal | 0 | 0 | 0 |
| Complete matched pairs correct | 2/4 | 0/4 | 2/8 |

The two legitimate refusals are the English documentation negatives. Complete-pair
success requires supporting selection on the positive **and** correct refusal on
the same question's negative, not merely selecting a source on both. The selector
scored 10/16 supported-selection-or-valid-refusal rows but only 2/8 complete pairs.
Always-positive, always-negative and documentation-only evidence-blind policies
each score 8/16 rows and 0/8 pairs. These are computed baselines, not extra model calls.
The modest result does not establish general semantic evidence sensitivity.

## Output structure and final delivery are different measurements

Both generation arms use exactly the same 14 selected contexts, prompts and sampling
settings. The branch schema changes whole-object alternatives and the answer length
bound; it does not change the final Python validator or fill citations afterward.
The other two rows stop at the selector and remain in end-to-end denominators.

| Outcome | Legacy schema | Branched schema |
|---|---:|---:|
| Downstream requests | 14 | 14 |
| Raw objects conform to that arm's wire schema shape | 14/14 | 14/14 |
| Pass final Python answer contract | 1/14 | 14/14 |
| Accepted supported correct answers | 1/8 offered positives | 7/8 offered positives |
| Accepted answers without supporting selected evidence | 0 | 6 |
| Accepted incorrect answer despite supporting selected evidence | 0 | 1 |
| Legitimate final refusal | 2/8 negatives | 2/8 negatives |
| Correct accepted answer or valid refusal | 3/16 rows | 9/16 rows |
| Complete final matched pairs correct | 1/8 | 2/8 |

Legacy's 13 invalid outputs all omitted citations. Those shapes were allowed by
the old wire schema, so these are **not** evidence of runtime schema noncompliance.
All 14 answer strings were unchanged between the two arms. The branch schema admits
six additional correct answers, but also admits six unsupported answers and one
incorrect answer. Better structural acceptance is not a semantic improvement or
safety gain. Legacy's accidental contract rejection is not a correct refusal either.

Three failure examples:

1. Chinese documented `MAX_FORM_PARTS` negative: selected a `MAX_FORM_MEMORY_SIZE`
   note and answered `500000`. It has a real source, but the wrong configuration key.
2. Both runtime-negative languages: answered `7` or `/orchid` from Willow's snapshot
   when asked about Orchid. A matching string does not bind the answer to the right entity.
3. English runtime-positive `APPLICATION_ROOT`: selected the correct `/orchid`
   snapshot but answered `orchid`. The leading slash is part of the configuration
   value. It is not normalized away and is scored incorrect in both arms.

No generator returned a refusal, so live behavior does not establish that the model
will choose the refusal branch appropriately. Its legal shape was tested offline.
See [all raw records](recorded/), [AI rationales](assistant-review.json), and
[replayed per-row/per-pair results](summary.json).

## Grammar capability boundary

The [pinned llama.cpp grammar documentation](https://github.com/ggml-org/llama.cpp/blob/b1b770d90d94cad9e9ea5b993bdbc383a522fb28/grammars/README.md#json-schemas--gbnf)
warns that only a schema subset is supported, with conditionals and uniqueness
limitations. This experiment uses whole-object `anyOf`, not mixed root properties
or `if/then`. The pinned release has no GBNF validator binary and its source tree
contains the C++ converter, not the old Python script referenced by stale prose.
No native grammar compiler/validator was run. [Preflight](preflight.json) means
original Python shape checks plus the existing Python contract, not native acceptance
of arbitrary strings. All actual server requests completed and the 14 branched
outputs passed the final contract, a narrower observed result.

Whitespace-only answers and duplicate citations still require Python rejection;
the schema does not prove semantic support or correct scope. No normalization,
unconditional citation filling or repair was performed. The production generator,
retrieval service and existing evidence gate are untouched.

## Reproduction and limitations

UTC run: 2026-11-17 16:11:00 to 16:13:06 (Nov 18 MYT), 16 selectors + 28 generations,
no retries, transport failures or incomplete completions. Pinned free CPU model and
runtime hashes are in [README](README.md) and [manifest](recorded/manifest.json).
The server stopped normally. Best-effort peak resident memory was `1279852 kB` on
this Linux run; no cross-date memory or latency comparison is justified.

The same model selects and answers, not an independent evaluator. The selected-only
generation comparison is conditional on this selector; the separate 16-row and
8-pair denominators prevent hiding upstream failures. Small synthetic structured
records are easier and less natural than broad real-world retrieval, and equal
character lengths do not equal tokenized compute. No production, agent-readiness
or universal correctness claim follows.

Attributed-QA supplies a useful conceptual distinction: condition claims on the
question and supplied evidence, rather than an answer string alone
([pinned primary repository](https://github.com/google-research-datasets/Attributed-QA/tree/01f114b203ac98e9374471d26dba5e5e07f93409),
[Apache-2.0 license](https://github.com/google-research-datasets/Attributed-QA/blob/01f114b203ac98e9374471d26dba5e5e07f93409/LICENSE)).
This is an original matched-evidence experiment, not a reproduction of its evaluator;
no external code, dataset, model or metric implementation was imported for that reference.
