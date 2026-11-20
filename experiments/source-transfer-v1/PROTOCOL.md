# Frozen two-new-source generation pilot

A curated new-source development pilot, not an independently sampled/held-out test.
Prior corpus/model experiments used Flask. CPython and Express are new to this
project's supplied evidence, but prior exposure in model pretraining is unknown.
Two source families, three setting fact families (suggest_on_error, allow_abbrev,
query parser), five release-specific/predicate targets, eleven conditions, each
in English and Chinese: 22 rows. Translations are correlated, not independent facts.

## Sources, intent and representation

Use short original reviewed summaries backed by exact release commits and whole
source/license SHA receipts. Full upstream source/tests stay outside the retrieval
pool and Git. They are an independent oracle reference, not snippets silently
available in negative conditions. The model receives only indexed summary text
and opaque IDs. Source-reference metadata is recorded for traceability but not sent.

CPython 3.14.0 suggest_on_error constructor default is Boolean False. Explicit
usage setting True and neighboring color default True do not answer that default
question. In 3.13.0 the constructor parameter is absent; presence is a separate
predicate, not a False/null/zero default. allow_abbrev=True in 3.13.0 is a stable
control. Express 4.21.2 query parser default is extended; 5.1.0 is simple. An
explicit extended example and trust proxy default are different predicates.

Current catalog claims use **canonical strings**, not native Boolean support:
"False", "True", "absent", "present", "extended", "simple". No False==0 coercion,
unit conversion, absent/null conflation or production schema modification. The
actual scope key carries `.default`, `.explicit_example`, or `.parameter_presence`;
separation is enforced by ClaimIndex, not merely descriptive text labels.

## Fixed actual retrieval and intervention

Each arm builds the same actual indexed pipeline and original BM25 over the same
per-case corpus. k=1 and 12000-character packing cap are fixed. Positives have two
records, negatives have one (a deliberate clear near-miss); this is not an equal-
shape evidence-substitution experiment. Queries retain space-separated technical
identifiers in Chinese; there is no hidden translation or glossary adaptation.

Ungated ranks all evidence. Scoped performs the existing complete reviewed catalog
preflight and eligibility intersection before requested top-k, retaining full-index
BM25 scores. No values/golds/source-oracle files are passed to ranking or generation.
Both arms use the same previous branched generator/prompt/schema/options, except
context and its allowed citation IDs. Scope filtering also changes context/allowed
IDs, not just a model reasoning variable. Defaults and historical artifacts stay
unchanged. There is no LLM gate/selector or automatic natural-language scope parser.

Before model execution freeze `preflight.json` from actual BM25/pipeline. It records
all full scores, packed IDs, support coverage, scope reasons and expected call count.
Every ungated row must have actual lexical context, including every negative.
The English CPython default positive may lose support at top-1; retain that observed
retrieval miss instead of tuning text, k or a threshold after generation.

Expected: 22 ungated calls, 10 scoped calls and 12 scoped no_matching_scope blocks.
Counterbalance arm order; do not retry or tune on model results. Use only the pinned
Qwen3.5-0.8B Q4_0 / llama.cpp b12359 CPU runtime, temperature0/seed42/max512/context4096,
four threads, thinking disabled. Incrementally save exact requests/raw responses,
model/runtime hashes and failure status. Preserve partial rows if interrupted.
Best-effort telemetry is not a performance comparison. No paid service or private data.

## Per-case rubric frozen before calls

Each case stores external gold, literal forms and offered supporting IDs **outside**
the actual pipeline request/catalog. Evaluate these axes separately:

1. Offered and actually packed support; a top-k miss is not a model reasoning error.
2. Actual model call, deterministic no-run by reason, transport error, invalid final
   contract, valid answered output or valid model abstention. Invalid/error is never
   credited as a successful abstention. No-run is never a correct model answer.
3. AI-reviewed typed answer truth using the external release oracle, regardless of
   supplied evidence. Unambiguous prose stating the exact value can be true; a
   negated or contradictory mention is not. For Boolean targets, bare 0, null,
   absent or unrelated truthy wording is wrong. Parameter absence is not False.
4. Citation support for the **full actual answer and requested version/predicate**
   using only the cited packed summaries. Correct external truth without such support
   is an accepted unsupported answer. Mere valid citation membership is insufficient.
   Every cited record must support the requested claim; extra wrong-scope references
   fail this conservative single-claim criterion. No automatic substring grading.
5. A separate prespecified strict surface metric requires the entire raw answer to
   equal one of the case's literal forms (False/false, True/true, or the exact string
   absent/extended/simple). No stripping, case repair, punctuation repair or extra
   prose in that metric. Semantic truth and strict literal form are not conflated.

Positive grounded success = accepted, oracle-true answer with full cited supplied
support, reported over all ten positive rows and per family/target/language. Also
report strict-literal grounded success. Correct-by-memory without support is not
grounded success. Refusal on a positive is a false refusal only if its final contract
is valid; invalid refusal-like text is reported separately. On negatives, separate
accepted unsupported factual claims, semantic nonanswers, valid model abstentions,
deterministic blocks and technical failures. A valid model abstention is legitimate
when supplied evidence is insufficient; invalid/transport failures earn no safety
credit. Do not collapse all non-answers into success.

Report matched improvements/regressions over these fixed rows, source/setting-family
and five target denominators. Also report both translations jointly, without population
confidence intervals. AI author + independent AI review is not human calibration.
No result establishes production reliability or readiness for autonomous agents.
