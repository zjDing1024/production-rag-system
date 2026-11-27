# Frozen CPython scope, units, and origin protocol

Freeze the record texts, machine-readable expected types/units/locators, fixed
questions, case membership, scope and scorer controls before any live response.
Use original reviewed summaries of pinned CPython 3.10.0 and 3.11.0. An offline
plan accepts only the reviewed integer+unit and exact evidence ID and source
URL; a wrong-method, missing-setting or lexical decoy does not inherit a fact
from any other scope. A separate unscoped top-1 BM25 probe is retrieval-only.

The optional live pilot is scoped-only, not a second causal comparison. Use the
same index, query and real BM25 top-1 as the offline plans. After retrieval, add
one fixed answer-format sentence to the wire query only: ask for a bare integer
followed by the word `seconds` without a period. Send at most three requests,
one for each registered eligible case, without retries. The two insufficient
cases stop before ranking and dispatch. Use the same pinned local
[asset manifest](../local-generation-smoke/sources.json), branched adapter,
temperature 0, seed 42, 512 max generated tokens, 4 CPU threads, one local
slot, loopback and no external tools.

Separate transport/schema, model abstention, deterministic stop, and answer
branches. For a valid answer branch, trim surrounding whitespace and require
ASCII nonnegative integer syntax (no leading zeros, max six digits), exactly one
space and the lowercase unit `seconds`. Verify integer value, unit, evidence ID
and exact source URL/locator separately. No prose paraphrases count as exact.
A literal numeric mention inside a wrong-method, negated or example-only
sentence is not the requested claim; frozen controls document these failure
modes, not an automatic natural-language judge. Preserve raw data; retries and
threshold tuning based on responses are not allowed.

This authored pilot neither samples current CPython behavior nor tests production
configuration, security, or general semantic support. No latency claims, networked
agent actions, arbitrary shell/SQL interface, paid APIs, or asset redistribution.
