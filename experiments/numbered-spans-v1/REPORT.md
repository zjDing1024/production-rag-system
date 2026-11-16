# Nov 17: IDs remove copying failures, not the evidence problem

The experiment completed successfully as an execution, but **neither arm yielded
an accepted, supported correct answer**. Numbered spans made source resolution
reliable within the constrained interface while still accepting irrelevant evidence
and refusing answerable questions. This is a useful failure boundary, not a reason
to enable this selector in the default application.

## Separate the layers

| Layer | Exact whole-span quote | Numbered span |
|---|---:|---:|
| Offered answerable evidence | 8/8 | 8/8 |
| Offered related-unanswerable questions | 8 | 8 |
| Contract-valid selector responses, including refusals | 0/16 | 16/16 |
| Valid selections resolved to original text | 0 | 11 |
| Selected evidence supports the actual question | 0/8 answerable | 6/8 answerable |
| Valid selections without support for the question | 0 | 5 |
| Legitimate selector refusal | 0/8 unanswerable | 3/8 unanswerable |
| False selector refusal | 0/8 answerable | 2/8 answerable |
| Selector contract failure | 16/16 | 0/16 |
| Downstream generator calls | 0 | 11 |
| Contract-valid generated answers | 0 | 1 (unsupported) |
| Accepted, supported correct answers | 0/8 answerable | 0/8 answerable |
| Legitimate downstream refusal | 0 | 0 |
| Transport errors / incomplete completions | 0 / 0 | 0 / 0 |

An invalid selector response is **not** a legitimate refusal. Zero quote-arm false
refusals is not success: that arm produced no valid decision at all. Offered coverage
is established by the curated pool and AI source labels; it is not retrieval recall.
Both arms constrain IDs with the same schema enum, so ID validity is not evidence
that the model can generate arbitrary correct citations without assistance.

Numeric/nonnumeric separation matters. The ID arm selected the correct span for all
four numeric answerable questions, but passed all four numeric runtime questions
without sufficient evidence. On the four nonnumeric answerable questions it selected
two correctly and falsely refused both X-Sendfile questions; it legitimately refused
three of four nonnumeric runtime questions. A numeric/non-numeric shortcut would not
be a general evidence-sufficiency solution.

## What actually came back

For the question about days remaining on **the user's current cookie**, the ID arm
selected the lifetime-default documentation, and the generator returned:

```json
{"answer":"31 days","citations":["1"],"abstain":false}
```

This is the only accepted generated answer in the run. It has a valid source ID,
but the source cannot establish an existing cookie's remaining lifetime. It is
therefore unsupported for the actual question, not a successful answer.

The other ten generator outputs failed the unchanged contract:

- Seven supplied nonempty answers with no citations. Five contain the correct
  requested documented fact (31 days, example port 5000, or the Chinese template
  debugging key); two incorrectly substitute the example port for actual production
  state. Raw factual correctness does not make a missing-citation answer accepted.
- Three set `abstain=true` but put `None` or `无法确定` in `answer`, which must be empty.
  Two express semantically appropriate refusal of unknown runtime facts; one falsely
  refuses the answerable English template-debugging question. None is a valid served
  refusal.

All 16 quote outputs claimed `sufficient=true`. Post-hoc inspection found seven
copied the exact span except for its final newline, while nine changed or omitted
other text. The frozen equality rule includes that newline. This reveals a brittle
interface requirement, not proof that all seven models failed to locate evidence.
No normalization or outcome-based rescoring was applied. Every model completion
reported `finish_reason=stop`; the largest completion was 130 tokens, below the
512-token limit. Partial quotations here are not labelled budget truncation.

[Per-case outcomes](summary.json), [AI reasons](assistant-review.json), and
[original requests/responses](recorded/) preserve both failures and successes.

## Fairness and limits

Both arms saw the **same question and ordered span texts**, not long chunks in one
arm and convenient short answers in the other. The fixed six-span pool was selected
before inference and used unchanged for every question. Only output instructions
and schema changed; the whole-span quote requirement intentionally includes a larger
output burden. This cannot isolate grammar causally. Extra downstream calls in the
ID arm also mean total compute differs; there is no equal-compute or speed claim.

Four facts, two languages and two evidence labels produce 16 questions, not 16
independent fact trials. They are AI-authored development targets on known Flask
documents, with AI cross-checks, not human evaluation or a held-out benchmark.
Some terms had appeared in earlier supplied document windows, but these were not
the old acceptance targets. Older questions are regression tests only. No tuning
was performed on the observed outcomes, and no model was trained or fine-tuned.

Selection proves neither entailment nor answer correctness. A future multi-source
claim may require the **joint** cited set even when no individual citation suffices;
individual relevance and joint support must not be conflated. ALCE's published
evaluation separates post-answer joint citation entailment from individual-citation
checks ([pinned primary code](https://github.com/princeton-nlp/ALCE/blob/246c476a4edfc564266b7346b6e29ef4861ae937/eval.py#L301-L429),
[MIT license](https://github.com/princeton-nlp/ALCE/blob/246c476a4edfc564266b7346b6e29ef4861ae937/LICENSE)).
That is conceptual context, not an imported implementation, data set, pre-answer
gate or result claimed here. Our exactly-one-span limit cannot validate joint-set
support; we imported no ALCE code/data and did not run its evaluator.

## Execution and reproduction

Recorded UTC window: 2026-11-16 16:19:47 to 16:22:14 (Nov 17 MYT).
32 selector + 11 generator calls on the pinned Qwen3.5-0.8B Q4_0 CPU runtime,
no retries, no paid resources, all server processes stopped by the runner.
Best-effort Linux telemetry observed peak resident memory `3929984 kB` (about
3.75 GiB). Single-run timings include startup, cache and order effects and are
not a performance benchmark. [Commands, sources and hashes](README.md).

No model weights, third-party executable, private information or service credentials
are included in this experiment. Original code uses the repository MIT license;
offered Flask excerpts retain the corpus BSD-3-Clause attribution. No default
behavior, existing gate or generator source file changed.
