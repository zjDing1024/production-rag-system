# PostgreSQL citation transfer: same number, different setting

This is a five-case offline acceptance replay of the existing finite-policy
document Agent on a new source family. It uses original reviewed summaries for
PostgreSQL 16.0 and 17.0. It runs real local scope preflight, top-1 BM25 and
citation validation; it does not query a database, execute SQL or a model, open
a locator, or add a new route to the default Agent CLI.

The pinned 17.0 documentation records integer default 0 for transaction_timeout
and statement_timeout, with milliseconds as the implied unit. This default
disables the corresponding timeout. The prepared-transaction exception is
separate, and by itself supplies neither the default nor unit. The 16.0
configuration chapter documents statement_timeout and idle_in_transaction_session_timeout,
not transaction_timeout. [The 17 release notes][release] describe the addition.

| Registered fixture case | Normal workflow result |
|---|---|
| 17.0 transaction timeout default, with both same-value neighbors indexed | Cites transaction timeout, integer 0 milliseconds |
| 17.0 statement timeout default, with neighbors indexed | Cites statement timeout, integer 0 milliseconds |
| Same 17.0 transaction question, only neighbor defaults | No matching scope, no answer or citation |
| 16.0 transaction intent, only 16.0 neighbors | No matching scope, no answer or citation |
| Same 17.0 transaction default question, only prepared-transaction exception | No matching scope, no answer or citation |

Observed: 2/2 cited positive results, 0/3 accepted negatives, all three negatives
stop in scope preflight, 5 agent retrieval attempts / 2 actual BM25 passes /
0 model calls. A separate BM25 diagnostic ranks each negative's available
records without applying the scope filter: 3/3 have lexical hits. These three
diagnostic passes are **not** Agent dispatch, and do not imply a baseline would
give an unsupported answer.

The exact answer type, unit, anchored locator and stop expectations were frozen
before implementing the replay in [oracle.json](oracle.json). It is separate
from the indexed records. The exact locator oracle also caught a boundary issue:
the legacy chunk renderer appends local summary line offsets to the locator,
even if it already contains upstream line anchors. The transfer adapter returns
the reviewed, exact upstream locator after the existing catalog provenance check;
summary text/offset/digest remain separate. The original ten-case acceptance
replay is byte-identical and the original CLI exposes no PostgreSQL registration.
This change does not migrate the old locator display or verify upstream entailment.

## Reproduce without network

    python -B experiments/postgres-agent-transfer-v1/replay.py --check
    python -B experiments/postgres-agent-transfer-v1/replay.py --case pg17-transaction
    python -B -m unittest discover -s experiments/postgres-agent-transfer-v1 -p 'test_*.py'

[Recorded traces](report.json) include the actual selected ID, scope and locator.
The same-version, wrong-setting and missing-default fixtures are designed, not a
blind sample, production security guarantee, arbitrary input path, or PostgreSQL
runtime reproduction. All five cases rely on pre-reviewed metadata.

[17.0 transaction default][t17] · [17.0 statement default][s17] ·
[17.0 idle neighbor][i17] · [16.0 statement neighbor][s16] ·
[16.0 idle neighbor][i16] · [Prepared-transaction exception][exc].
Upstream documents use the [PostgreSQL License][license]. The project includes
only original short MIT fixture summaries and source links, not upstream text.

[t17]: https://github.com/postgres/postgres/blob/d7ec59a63d745ba74fba0e280bbf85dc6d1caa3e/doc/src/sgml/config.sgml#L9368-L9382
[s17]: https://github.com/postgres/postgres/blob/d7ec59a63d745ba74fba0e280bbf85dc6d1caa3e/doc/src/sgml/config.sgml#L9332-L9346
[i17]: https://github.com/postgres/postgres/blob/d7ec59a63d745ba74fba0e280bbf85dc6d1caa3e/doc/src/sgml/config.sgml#L9441-L9454
[s16]: https://github.com/postgres/postgres/blob/c372fbbd8e911f2412b80a8c39d7079366565d67/doc/src/sgml/config.sgml#L9118-L9132
[i16]: https://github.com/postgres/postgres/blob/c372fbbd8e911f2412b80a8c39d7079366565d67/doc/src/sgml/config.sgml#L9191-L9204
[exc]: https://github.com/postgres/postgres/blob/d7ec59a63d745ba74fba0e280bbf85dc6d1caa3e/doc/src/sgml/config.sgml#L9396-L9400
[release]: https://www.postgresql.org/docs/17/release-17.html
[license]: https://www.postgresql.org/about/licence/

## Optional live CPU comparison: five fixed requests, seven actual calls

The opt-in compared path uses the same reviewed index and BM25 as the offline
transfer above, not a model embedded in the Agent. Run in Linux x86_64:

```bash
# Inspect real top-1 evidence and audit the recorded run without local assets:
python -B experiments/postgres-agent-transfer-v1/compare_live.py --plan
python -B experiments/postgres-agent-transfer-v1/compare_live.py --check
# Only for an explicit new CPU run; free public assets (~586 MB), no SQL:
python -B experiments/evidence-sufficiency-v1/prepare_assets.py --directory /tmp/rag-local-assets
mkdir -p build
python -B experiments/postgres-agent-transfer-v1/compare_live.py --assets /tmp/rag-local-assets > build/postgres-live.json
```

The [protocol](LIVE-PROTOCOL.md) and [file lock](live.lock.json) were fixed
before inference (lock SHA-256
`7b4535424e5287da47bf49ad654b5cd4ab02f8cb073c982ff43452a325bd8e59`).
The [full receipt](recorded-live.json) retains each reviewed outcome,
context, actual payload and raw envelope. The `--check` command verifies the
hash and reruns retrieval plus response validation from the captured envelopes,
not the model. Runtime: pinned [llama.cpp b12359 (MIT)](https://github.com/ggml-org/llama.cpp/blob/b1b770d90d94cad9e9ea5b993bdbc383a522fb28/LICENSE)
and [Qwen3.5-0.8B Q4_0](https://huggingface.co/ggml-org/Qwen3.5-0.8B-GGUF/tree/004fd086eccea9f7cf867aa07ba328773beef81d)
([base-model Apache-2.0 license](https://huggingface.co/Qwen/Qwen3.5-0.8B/blob/2fc06364715b967f1860aea9cf38778875588b17/LICENSE)).
The pinned runtime's [JSON response-format docs](https://github.com/ggml-org/llama.cpp/blob/b1b770d90d94cad9e9ea5b993bdbc383a522fb28/tools/server/README.md)
describe schema constraints, not citation truth. No weights or upstream code are
included.

| Recorded outcome | Unscoped top-1 | Scoped top-1 |
| --- | ---: | ---: |
| Model requests | 5 | 2 |
| Positive answers citing the correct reviewed source | 2/2 | 2/2 |
| Positive passes under pre-frozen bare-value plus citation scorer | 0/2 | 0/2 |
| Negative prompts taking a valid answer branch without question support | 3/3 | 0/3 |
| Negative prompts stopped before ranking/model dispatch | 0/3 | 3/3 |
| Model abstentions / invalid responses / transport errors | 0 / 0 / 0 | 0 / 0 / 0 |

Separate post-run review: the two positive outputs in each arm explicitly
state the correct setting's default is 0 milliseconds, with its exact
reviewed citation. Detected correctly by direct reading of the four outputs,
but they are complete sentences, so the pre-frozen scorer classifies them as
`noncanonical_answer`. Its rules and recorded totals were not changed.

For the PG17/PG16 neighbors-only questions, the unscoped model cited the idle
setting and wrote about that setting instead of the asked transaction timeout.
Those statements can be true about their cited neighbor and still fail to
answer the question; neither establishes the requested claim. For the
prepared-exception-only question it returned the string `"None"` with
`abstain=false` and cited the exception. This is a nonanswer in the
answer branch, not a model abstention or a verified default. All three
unscoped negative citations satisfied literal context membership. The scoped
stops are deterministic policy results, not safer model behavior.

These are five designed cases, with two evidence removals reusing the exact
PG17 question, not five independent trials or a model accuracy estimate.
No production workload, PostgreSQL runtime, arbitrary SQL, or prompt/tool
behavior is tested.

Locator display caveat: the raw live pipeline context inherits the generic
chunk citation renderer, which appends local line coordinates (`#L1-L1`)
after the upstream `#L…-L…` anchor. Those composite strings are not usable
source locators. The literal model citations here are **chunk IDs**; source
anchors for the exact reviewed target come from [the frozen oracle](oracle.json).
The two offline Agent examples above use canonical source URLs separately.
