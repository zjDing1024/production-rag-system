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
