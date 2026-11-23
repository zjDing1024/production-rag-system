"""Synthetic SQLite evidence summaries and a separately callable runtime oracle."""

from dataclasses import dataclass
import sqlite3


@dataclass(frozen=True)
class Identity:
    schema: str
    table: str
    column: str
    operation: str
    field: str

    @property
    def key(self):
        return ".".join((self.schema, self.table, self.column, self.operation, self.field))


TARGET = Identity("main", "measurement", "derived", "table_xinfo", "hidden")
WRONG_OBJECT = Identity("temp", "measurement", "derived", "table_xinfo", "hidden")
WRONG_FIELD = Identity("main", "measurement", "derived", "table_xinfo", "cid")
MISSING = Identity("main", "measurement", "derived", "table_info", "presence")
QUESTION = "In SQLite 3.46.1, what is the table_xinfo hidden field for main.measurement.derived?"
FIXTURE_ID = "sqlite-generated-column-v1"
DDL = (
    "CREATE TABLE main.measurement(raw INTEGER, aux1 INTEGER, aux2 INTEGER, "
    "derived INTEGER GENERATED ALWAYS AS (raw + 1) STORED)",
    "CREATE TABLE temp.measurement(raw INTEGER, aux1 INTEGER, aux2 INTEGER, "
    "derived INTEGER GENERATED ALWAYS AS (raw + 1) STORED)",
    "CREATE TABLE main.virtual_measurement(raw INTEGER, aux1 INTEGER, aux2 INTEGER, "
    "derived INTEGER GENERATED ALWAYS AS (raw + 1) VIRTUAL)",
)
# Deliberately single-field snapshots: do not give rejected arms a whole PRAGMA row.
# These are original descriptions of the reproducible synthetic case, not official records.
EVIDENCE = {
    "main-hidden": (TARGET, 3, "SQLite 3.46.1 fixture: main.measurement.derived table_xinfo hidden is 3."),
    "temp-hidden": (WRONG_OBJECT, 3, "SQLite 3.46.1 fixture: temp.measurement.derived table_xinfo hidden is 3."),
    "main-cid": (WRONG_FIELD, 3, "SQLite 3.46.1 fixture: main.measurement.derived table_xinfo cid is 3."),
    "table-info": (MISSING, "absent", "SQLite 3.46.1 fixture: main.measurement.derived is not returned by table_info."),
}


def runtime_oracle():
    """Run SQLite only in memory; do not use its full rows in retrieval."""
    connection = sqlite3.connect(":memory:")
    try:
        for ddl in DDL:
            connection.execute(ddl)
        version, source_id = connection.execute("SELECT sqlite_version(), sqlite_source_id()").fetchone()
        pragmas = {
            "main_xinfo": "PRAGMA main.table_xinfo(measurement)",
            "temp_xinfo": "PRAGMA temp.table_xinfo(measurement)",
            "virtual_xinfo": "PRAGMA main.table_xinfo(virtual_measurement)",
            "main_info": "PRAGMA main.table_info(measurement)",
        }
        rows = {}
        for label, sql in pragmas.items():
            fields = ("cid", "name") if label == "main_info" else ("cid", "name", "hidden")
            cursor = connection.execute(sql)
            indexes = [next(i for i, pair in enumerate(cursor.description) if pair[0] == f) for f in fields]
            rows[label] = [dict(zip(fields, (row[i] for i in indexes))) for row in cursor]
        return {"version": version, "source_id": source_id, "rows": rows, "ddl": list(DDL), "queries": pragmas}
    finally:
        connection.close()
