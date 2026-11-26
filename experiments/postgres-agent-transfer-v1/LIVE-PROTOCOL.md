# Frozen PostgreSQL scope vs unscoped top-1

Reuse the exact five questions, source locators, candidate sets and per-case
evidence oracle from the offline transfer, without rephrasing a question or
adding distractors after observing any model answer. The two arms use one
index per case, the same top-1 BM25 (full-index statistics), 512 context
characters, and the exact same already-audited branched JSON adapter. The sole
arm switch is `scope_gate`. Alternate unscoped/scoped order across rows: five
unscoped requests and two scoped requests, one call per admitted arm, no
retry. Scoped negatives must stop before ranking with `no_matching_scope`.
The offline Document Agent is unchanged; the generator is a separate optional
experiment through the shared underlying pipeline, never an Agent tool.

Use the public asset [manifest](../local-generation-smoke/sources.json)
(Qwen3.5-0.8B Q4_0 and llama.cpp b12359, fixed checksums). One CPU-only server
binds loopback with no agent or web UI, one slot and four CPU threads. Prompt,
temperature 0, seed 42 and max 512 tokens come unchanged from the fixed adapter.
The runner records the model envelope and payload and checks the payload against
the same adapter across both arms. Runtime or hardware may change reproducibility
even at fixed temperature/seed; offline audit instead replays the actual record
through retrieval and the adapter.

For a contract-valid answer, first record exact citation IDs in the supplied
context. Membership is not attribution. The accepted display value is narrowly
an entire trimmed ASCII `0 ms` or `0 milliseconds` value (optional horizontal
spacing, singular form, case variation, terminal period). Other output syntax
is unscored, including longer explanations; record it verbatim and do not infer
it is false or a refusal. A positive is correct and supported only if this value
is displayed and its sole citation is the exact reviewed default-setting chunk
from the frozen oracle. A valid answer with a wrong or missing required evidence
target is unsupported; if the correct target is cited but the value is outside
the accepted syntax, report noncanonical instead.

Truth about the named setting is separate: on the PostgreSQL 17.0 questions the
value 0 ms is independently documented even when only decoys are presented.
On the PostgreSQL 16.0 transaction_timeout question, claiming that default
is false for the pinned documentation because the setting was not yet present.
The PG17 prepared-transaction exception does not establish its default. Do not
score a deterministic stop as a model abstention; record model abstention,
invalid schema/response, transport failure, and deterministic stop separately.
If a raw result cannot be replayed from the captured envelope, keep the
execution evidence and flag the offline reproduction limit.

This is one authored family and a diagnostic top-1 comparison, not a held-out
evaluation, model leaderboard or semantic verifier. No PostgreSQL instance,
SQL, arbitrary tools or paid resources are involved.
