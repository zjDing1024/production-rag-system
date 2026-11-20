# Measured CPython/Express indexed generation pilot

2026-11-21 MYT. One completed pinned CPU run, 32 actual model requests, zero retries,
all raw envelopes retained and owned server stopped normally. No training, paid
service, private data, default change or mutation of historical experiments.

## Frozen population and scope

Two new **supplied-source families** (CPython and Express), three setting fact
families (`suggest_on_error`, `allow_abbrev`, `query parser`), five release-specific
predicate targets, eleven conditions translated into EN/ZH: **22 rows per arm**.
Ten rows are answerable from offered summaries; twelve are missing the requested
version/predicate. Translations and same-question conditions are correlated. These
are curated source-informed development cases, not new independent facts per row,
blind external sampling or evidence that model pretraining never saw these sources.

CPython targets distinguish 3.14.0 Boolean default False, 3.13.0 parameter absence,
and stable allow_abbrev=True. Express targets distinguish 4.21.2 extended from
5.1.0 simple. Wrong-version, explicit-setting and nearby-field negatives have one
clear near-miss each; positives have two records. This is not an equal-shape
controlled evidence-substitution design. Both arms see identical offered data
within each case, and differ only through the opt-in scope pipeline.

## Retrieval coverage before inference

All 22 ungated rows have real lexical hits, including all twelve negatives. The
frozen actual BM25 preflight gives packed positive support **9/10 ungated, 10/10
scoped**. The English CPython suggest_on_error default question ranks the explicit
True usage example above the False default summary at k=1. Eligibility before
requested top-k rescues the latter, using the original full-corpus BM25 score.
The other nine positives already have supporting top-1 evidence in both arms.

The pure wrong-version negatives actually pack the older `p13presence` or
`e4default` records, not a same-version distractor. Explicit and near-field negatives
also pack their intended evidence, verified before calls. Canonical question strings
and actual scores/packed IDs are preserved in [preflight.json](preflight.json).
No ranking/text/k/threshold was tuned after generation. The old complete reviewed-
claim preflight remains active, but this pilot has no same-scope contradictory
bucket and does not add a new conflict-detection result.

## Outcome layers, not one inflated success percentage

| Layer | Ungated | Scoped |
|---|---:|---:|
| Offered positive / negative rows | 10 / 12 | 10 / 12 |
| Actual model calls | 22 | 10 |
| Final contract-valid `answered` | 22 | 10 |
| Deterministic `not_run/no_matching_scope` | 0 | 12 |
| Valid model abstentions | 0 | 0 |
| Invalid output / transport failures | 0 / 0 | 0 / 0 |
| Supported, oracle-correct accepted positive answers | 9 / 10 | 10 / 10 |
| Strict literal grounded positive answers | 9 / 10 | 10 / 10 |
| Accepted answer branches without cited support, all rows | 13 | 0 |
| Accepted negative answer branches without support | 12 / 12 | 0 / 12 |
| Correct-by-oracle but unsupported accepted factual answers | 0 | 0 |

The scoped result is **ten model answers plus twelve deterministic stops**, not
22 correct model answers or twelve learned refusals. Technical failures happened
zero times; the evaluator would not credit them as abstentions. No correct-by-memory
unsupported answer happened here, but truth and support remain separate fields.

The sole positive improvement is `py-default-supported-en`: ungated returns `None`
with citation `p14explicit`; scoped returns literal `False` citing `p14default`.
This is a documented retrieval/eligibility rescue, not improved reasoning on the
same evidence. The nine other positives remain correct, with no positive regression.
Conditional on genuinely supporting packed context, outputs are 9/9 and 10/10 here;
these tiny conditional denominators do not replace the all-positive 9/10 and 10/10.

### All twelve unsupported negative branches remain counted

Nine are concrete wrong factual answers:

| Raw negative output | Count | Error |
|---|---:|---|
| `不存在` | 1 | Transfers 3.13 parameter absence to a 3.14 default question |
| `True` | 2 | Transfers neighboring color default to suggest_on_error |
| `extended` | 4 | Transfers old-version or explicit-example mode to the 5.1.0 default |
| `false` | 2 | Transfers trust proxy value to query parser enum |

The other three negative outputs are the bare string `None`, all with a citation
and `abstain=false`. After reading the output, AI reviewers conservatively classified
these as **ambiguous null-like nonanswers**: the string might mean a null default
or “no answer,” but the output does not establish which. It is neither the correct
Boolean False nor a valid model abstention. The positive failure is also `None`,
so there are four such outputs overall. This disclosed semantic subcategory does
not reduce the primary denominator of twelve unsupported accepted negative branches.
Under a direct-value interpretation all twelve negatives are wrong answer branches;
under the conservative split there are nine concrete false claims plus three
ambiguous nonanswers. Neither interpretation gives refusal or correctness credit.

## Family and target counts

| Source family | Positive grounded, ungated → scoped | Negative unsupported branches, ungated | Scoped negative no-runs |
|---|---:|---:|---:|
| CPython | 5/6 → 6/6 | 6/6 | 6 |
| Express | 4/4 → 4/4 | 6/6 | 6 |

| Setting fact family | Positive grounded, ungated → scoped | Negative rows |
|---|---:|---:|
| argparse.suggest_on_error (default and presence predicates) | 3/4 → 4/4 | 6 |
| argparse.allow_abbrev | 2/2 → 2/2 | 0 |
| Express query parser | 4/4 → 4/4 | 6 |

| Release-specific target | Positive grounded, ungated → scoped | Negative rows |
|---|---:|---:|
| CPython 3.14.0 suggest_on_error default | 1/2 → 2/2 | 6 |
| CPython 3.13.0 suggest_on_error parameter presence | 2/2 → 2/2 | 0 |
| CPython 3.13.0 allow_abbrev default | 2/2 → 2/2 | 0 |
| Express 4.21.2 query parser default | 2/2 → 2/2 | 0 |
| Express 5.1.0 query parser default | 2/2 → 2/2 | 6 |

Both translations are grounded-correct jointly for four of five targets ungated,
five of five scoped. Negative outcomes are not present for every target, so this
is not balanced evidence of universal refusal ability. Do not attach population
confidence intervals or imply five independent source families.

## Protocol integrity, source limits and tests

The cases, per-case rubric, scope keys, loss policy, actual lexical coverage,
runner/prompt/schema and model/runtime hashes were frozen before calls. Arm order
was counterbalanced. Both arms reuse the identical earlier branched generator,
with unchanged prompts/settings except selected text and allowable citation IDs.
Filtering changes distractors, context length and allowable IDs, so no causal
claim about model reasoning or arbitrary context trimming follows.

Full upstream source/test/license bytes were pinned and inspected outside the
repository. The source oracle is separate from supplied summaries, not multiple
independent gold standards. CPython AST checks establish literal signature facts;
no upstream CPython 3.14 or Express behavior tests were run. Original summary quote/
hash bindings establish those authored bytes, not verbatim upstream spans. Public
PSF-2.0/MIT source pointers are in [the manifest](source-manifest.json); no upstream
source files or model binaries are published.

The scorer independently records external typed truth and support for the whole
answer from the **cited packed summaries**. Author and independent AI reviewer read
all 32 raw outputs and agreed. These are AI annotations, not human-calibrated or
automatically proven entailment. The canonical-string type deliberately keeps
False apart from integer 0, null, absence and an explicit True example.

18 new model-free tests validate fixture rebuilding, actual preflight, IDs/intents,
string typing, source separation, request/hash replay, tampering and no-run credit.
All 206 prior tests and historical audits are preserved. CI adds only offline
replay/tests, not model downloads. Telemetry/durations are best-effort observations,
not comparative latency/RSS claims. The project remains an opt-in prototype with
trusted reviewed metadata, not general RAG reliability or autonomous-agent readiness.
