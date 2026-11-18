# Opt-in typed scope filter

This is an exact metadata filter, not an evidence-sufficiency model, authorization
layer, natural-language scope parser or automatic retrieval integration. Existing
retrieval and generation defaults are unchanged.

## Offline CLI

From the repository root, with Python 3.10+ and no extra dependencies:

```bash
PYTHONPATH=src python -m rag_foundation.scope_gate \
  experiments/typed-scope-v1/example-input.json --gate
```

With no `--endpoint`, the CLI only plans the request. It neither downloads a model
nor calls one. The example keeps record `q7`, the Flask 1.1.4 summary, and rejects
`m2`, the 3.1.2 summary, with `version_mismatch`. Omitting `--gate` keeps both.

Input has exactly `query`, `scope`, and `records`. Each scope has exactly:

| Field | Documentation | Runtime |
|---|---|---|
| `kind` | `documentation` | `runtime` |
| `subject` | Project name | Application/entity name |
| `key` | Setting name | Observed property |
| `version` | Nonempty version string | JSON `null` |
| `observed_at` | JSON `null` | Canonical UTC second, `YYYY-MM-DDTHH:MM:SSZ` |

Each record has `record_id`, the same typed `scope` fields, `text`, and `citation`.
IDs are opaque and retained, not re-numbered by relevance. HTTPS and `synthetic://`
citation identifiers are accepted as labels only; this module does not fetch them.
Exact case-sensitive equality is used. No version-range logic, timestamp rounding,
case folding, whitespace repair or natural-query interpretation occurs.

Limits: 12 records, 4,000 characters per text, 12,000 total text characters,
2,000 query characters, 100,000 bytes for a CLI input file. Duplicate IDs, invalid
calendar timestamps, unknown/missing fields and wrong types are rejected. These
bounds are input contracts, not a production security review.

## Python API and states

```python
from rag_foundation.scope_gate import parse_input, plan, answer

query, scope, records = parse_input(input_document)
preview = plan(query, scope, records, gate_enabled=True)
# Explicit generator dependency; nothing runs when no scope matches.
result = answer(query, scope, records, generator, gate_enabled=True)
```

`gate_enabled=False` is the default. `select_scope` exposes rejected IDs and
field-level mismatch codes. It matches only kind, subject, key, version and time.
It does not compare answer values or access evaluation labels.

- Matching records + offline plan: `planned/generator_not_requested`.
- No matching records: `not_run/no_matching_scope`, `generator_called=false`.
- Otherwise the supplied generator's `answered`, `evidence_abstained`,
  `invalid_response` or `transport_error` result is retained unchanged.
- `semantic_support` always remains `unverified`.

A no-run is not a model refusal or successful inference. Literal text `None` in a
matching document is a value, not an absent record. With an explicit loopback
`--endpoint`, the CLI uses the existing production `LocalGenerator` unchanged.
The recorded controlled experiment instead explicitly injects the same prior
branched experimental generator into **both** arms. Its format improvement is
not silently installed as a production default.

## Trust boundary and deliberate counterexamples

The caller must provide correct scope metadata and ensure the natural-language
question agrees with it. A record can label itself Flask 1.1.4 while its text says
something false; it will still match. A question asking about 3.1.2 with a typed
1.1.4 request will still filter for 1.1.4. Unit tests preserve these failures as
limitations, not capabilities. Multiple conflicting records in the same scope
also all pass; this is not conflict resolution or semantic entailment.

The experiment manually establishes query/scope agreement and the meaning of its
small public-document/synthetic records. Its outcome cannot establish that an
untrusted production metadata feed is safe or correct.

## Design reference and evidence

Exact field comparison was written originally for this project. Conceptual
reference: Qdrant's explicit metadata matching separates field comparisons from
text handling in [pinned condition-checker source](https://github.com/qdrant/qdrant/blob/23065a0bf6857c3e5da45f6c8939cc746cc0580e/lib/segment/src/payload_storage/condition_checker.rs#L224-L237),
under [Apache-2.0](https://github.com/qdrant/qdrant/blob/23065a0bf6857c3e5da45f6c8939cc746cc0580e/LICENSE).
No Qdrant code or dependency was imported. This is a conceptual reference, not a
claim that Qdrant implements this experiment or verifies semantic support.

[Protocol](../experiments/typed-scope-v1/PROTOCOL.md) ·
[Measured results](../experiments/typed-scope-v1/REPORT.md) ·
[Reproduction](../experiments/typed-scope-v1/README.md)
