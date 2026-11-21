# Explicit release binding on a scoped RAG request

A strict opt-in guard checks **one ASCII release token** in the free-text question
against the existing typed documentation scope. It stops before per-request
catalog assessment, BM25 scoring, packing or generation when the release cannot
be bound. A match forwards the original question unchanged to the existing
index-owned scope and reviewed-value preflight. The existing CLI, API, scoring
and historical runs remain unchanged.

## Offline replay and invocation

From the repository root, standard-library Python 3.10+:

```bash
python experiments/version-binding-v1/replay.py --check
PYTHONPATH=src python -m unittest discover -s tests -p test_version_bound.py -v
PYTHONPATH=src python -m rag_foundation.version_bound --help
```

The standalone module CLI accepts the existing `--chunks`, `--catalog` and
`--request` format described in [the indexed pipeline documentation](../../docs/indexed-scope-pipeline.md).
Use `-k 1` for this experiment. Without an explicit loopback `--endpoint` it only
plans. The Python API is
`answer_with_version_binding(pipeline, query, scope, k=1)`. It returns a
`binding` decision, and after a match only, the original `pipeline` output.

This is literal agreement, not release intent, identity, authorization,
fact understanding, model refusal, or semantic support verification.
The scope requires a canonical ASCII `major.minor.patch`; the question may
prefix its single mention with lowercase `v`. A leading zero, symbolic range,
build metadata, prerelease, wildcard, two mentions (even the same version twice),
or missing token is out of contract. Unicode prose around an ASCII version is
allowed. Natural-language negation, version comparisons expressed in prose,
product, setting and intention are not inferred or verified. A question about
another project mentioning the same literal can pass and even pack a passage
if the catalog supports the caller's scope. Trusted scope assignment and
catalog completeness remain requirements, and no parser behavior below is a
security boundary.

## Actual retrieval replay, no model

The [recorded report](report.json) uses the original reviewed Express summaries
from the [prior CPU experiment](../source-transfer-v1/REPORT.md) as evidence.
Express 4.21.2 sets the application default to `extended` and Express 5.1.0 sets
it to `simple`, from [4.21.2 source](https://github.com/expressjs/express/blob/1faf228935aa0a13111f92c28ee795be64ce3f0f/lib/application.js#L80-L86)
and [5.1.0 source](https://github.com/expressjs/express/blob/cd7d4397c398a3f3ecadeaf9ef6ac1377bd414c4/lib/application.js#L93-L100)
under [MIT](https://github.com/expressjs/express/blob/cd7d4397c398a3f3ecadeaf9ef6ac1377bd414c4/LICENSE).
No upstream implementation or test code is copied. The unrelated record uses
the existing CPython summary and [source/license receipts](../source-transfer-v1/source-manifest.json).

Keep both release records in one complete catalog. Cross the two release-specific
questions with the two caller scopes at k=1. Both arms use the same old scope
gate, and only one arm adds the new literal binding. EN/ZH are paired translations
from **one** fact family, not independent samples.

| Offline outcome | Existing scope only | Scope + release binding |
| --- | ---: | ---: |
| Matching questions pack matching evidence | 4/4 | 4/4 |
| Crossed questions pack wrong-release evidence | 4/4 | 0/4 |
| Crossed requests rejected before query execution | 0/4 | 4/4 |
| Model requests | 0 | 0 |

Separately, use identical extra CPython chunk bytes either with an assigned
unrelated scope or without its catalog entry. The supported request still packs
the correct Express evidence with the assignment, but stops before ranking as
`catalog_incomplete` without it. The old-release-only negative goes from
`no_matching_scope` to `catalog_incomplete`. Both stop causes are preserved after
a successful version binding. A complete catalog with only explicit-set evidence
in the right version still returns `no_matching_scope` for the default-value
predicate. These are scoped retrieval/control outcomes, not answer accuracy.

## Six live CPU calls on the English crossing

The narrower live check freezes only the four English question/scope pairs
above. Both arms use the same fixed generator and original question; there are
no model calls for the unrelated-catalog controls. Inputs, adapter, settings
and scoring rules were [fixed before generation](LIVE-PROTOCOL.md) and hashed in
[the lock](live.lock.json). The raw loopback record and all four paired decisions
are preserved.

| Model or deterministic outcome | Existing scope only | Scope + release binding |
| --- | ---: | ---: |
| Model requests | 4 | 2 |
| Correct and cited-supported on diagonals | 2/2 | 2/2 |
| Valid answer, false for question, and unsupported on crossed inputs | 2/2 | 0/2 |
| Deterministic no-run on crossed inputs | 0/2 | 2/2 |
| Model abstention, invalid output, transport error | 0 | 0 |

Without binding, asking about 4.21.2 with scope 5.1.0 returns `simple` citing
`e5default`; the inverse returns `extended` citing `e4default`. Both outputs
satisfy the schema and cite a supplied chunk, but both are wrong and unsupported
for the **version in the question**. The two blocked crossed cases are not model
refusals. On the diagonals, the returned exact values and citations agree across
arms. This is one paired setting fact, not a model performance claim.

```bash
# No model, network access or download:
python experiments/version-binding-v1/audit_live.py --check

# Optional exact-input real CPU rerun on Linux x86_64; free public assets (~586 MB)
python experiments/evidence-sufficiency-v1/prepare_assets.py --directory /tmp/rag-local-assets
mkdir -p build
python experiments/version-binding-v1/live.py --assets /tmp/rag-local-assets > build/my-version-binding-live.json
```

[Raw requests/envelopes](recorded-live.json) · [SHA-256](recorded-live.sha256) ·
[Exact truth/support per case](live-summary.json) ·
[Model/runtime and license references](../local-generation-smoke/sources.json).
The audit verifies raw/frozen hashes, reruns retrieval and the adapter with the
recorded envelopes, and scores exact enum plus required cited source. It does
not replay inference or establish general semantic entailment. The live runner
checks asset hashes, launches one loopback CPU server with no agent, web UI or UI
MCP proxy, and stops it even on failure. No credentials, GPU or paid services.
