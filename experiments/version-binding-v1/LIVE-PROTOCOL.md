# Fixed CPU version-crossing follow-up

Use the English 2×2 question/scope crossing from the offline record, both arms
scoped, one adding literal binding. The two diagonal pairs should retain correct
support. Two crossed scoped-only rows are intentionally paired with the wrong
version. Their reference is still the version named in the original question.

Fixed prior branched generator, Qwen3.5-0.8B Q4_0 and llama.cpp b12359, zero
temperature, seed 42, output at most 512 tokens, context 4096 and four CPU threads.
All model settings, retrieval inputs, k=1 and original query text are fixed.
Expect at most six actual loopback requests (four unbound and two bound), no
retry or threshold tuning. Model requests and model returns are recorded verbatim.

Judge separately: model called/not called and reason; strict adapter contract;
whether the complete answer states the exact setting value for the release in
the question; whether its cited packed record supports that specific release
and predicate. A correct remembered value from a wrong-version passage is true
but unsupported. A format-valid refusal with no citations earns no factual
answer credit. Deterministic not-run is not model refusal. Count only four
matched pairs (English only) and one source fact family; no generalization.
