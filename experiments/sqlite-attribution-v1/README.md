# Same value, wrong SQLite evidence

This four-case offline acceptance replay keeps one question and one answer value fixed.
It compares the existing release-and-catalog pipeline with an extra, trusted **fixture
request-to-scope binding**. The binding knows exactly one authored question and its
expected scope. It is not a production feature or a free-text scope parser.

## Sources and runtime

- The retrieval records are original, synthetic documentation-style summaries labeled
  SQLite **3.46.1**, based on the [tagged implementation][old-source]. They are not
  upstream quotes, actual database records, or claims about the runtime used here.
- The independent [in-memory oracle transcript](runtime-oracle.json) was run on SQLite
  **3.53.1** through Python's standard-library sqlite3. It records the linked library's
  version and source ID, the DDL and PRAGMAs; the full rows are not searchable evidence.
  The [3.53.1 Git source][runtime-source] also implements separate column index and
  hidden flags; its Fossil origin matches the hash in the reported runtime source ID.
- Official [PRAGMA references][pragma] distinguish table_info from table_xinfo.
  SQLite is [public domain][license]. No upstream code is copied.

Both STORED tables have a derived column with (cid, hidden) = (3, 3). A separate
VIRTUAL table has (3, 2) as an oracle sanity control, not a fifth retrieval case.
Main table_info lists the three ordinary columns and omits the generated column.

## Actual BM25 and citation-support results

Each arm calls the existing top-1 scoped retriever when allowed. The supported case and
both crossed cases contain the same three indexed chunks, including the correct one.
Each crossed request passes the release check, finds a genuine lexical hit under
its supplied scope and packs the wrong source. The fourth catalog is complete but
contains only table_info material, with no matching table_xinfo hidden scope.

| Case | Existing release and scope path | Added fixture binding |
|---|---|---|
| Supported | Packs main hidden=3; correct value and scope | Same |
| Wrong object | Packs temp hidden=3; equal value, wrong schema/object | Mismatch stops before ranking |
| Wrong field | Packs main cid=3; equal value, wrong field | Mismatch stops before ranking |
| Missing field | no_matching_scope | Binding passes; no_matching_scope |

Value scoring reads the selected **fixture candidate value**, not a generated response.
Citation support requires the exact schema, table, column, PRAGMA and output field in
the question. Baseline yields one exact supported plan and two exact-but-unsupported
plans; binding keeps one supported plan and stops both crossed cases. When no evidence
is packed, value/support are unscored rather than false. Both arms call the model zero
times. These are one fact family and four correlated designed cases, not model accuracy,
learned abstention, or a generalized or security guarantee. No production default changes.

## Reproduce

From the repository root, offline and without external packages:

    python experiments/sqlite-attribution-v1/replay.py --check
    python experiments/sqlite-attribution-v1/replay.py --oracle
    python -m unittest discover -s experiments/sqlite-attribution-v1 -p 'test_*.py'

The first command checks [the frozen retrieval report](replay.json) byte-for-byte.
The second measures whatever SQLite library is linked to Python; its version/source
identity may differ from the recorded transcript. Tests require the expected PRAGMA
behavior, not the same runtime build.

[old-source]: https://github.com/sqlite/sqlite/blob/f3d536d37825302e31ed0eddd811c689f38f85a3/src/pragma.c#L1198-L1243
[runtime-source]: https://github.com/sqlite/sqlite/blob/ccd445d76a9362c63add000354fac84ba9022176/src/pragma.c#L1200-L1260
[pragma]: https://sqlite.org/pragma.html#pragma_table_xinfo
[license]: https://sqlite.org/copyright.html
