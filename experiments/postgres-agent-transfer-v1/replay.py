"""Offline transfer of the existing read-only workflow to five frozen cases."""

import argparse
import json
from pathlib import Path
import sys
from types import MappingProxyType

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "src"))

from rag_foundation.corpus import canonical_json, digest
from rag_foundation.safe_document_agent import DocumentAgent, Intent, Record
from rag_foundation.scope_gate import Scope

RELEASES = {
    "16.0": "c372fbbd8e911f2412b80a8c39d7079366565d67",
    "17.0": "d7ec59a63d745ba74fba0e280bbf85dc6d1caa3e",
}
ORACLE_SHA256 = "bc272fa94f58fe78f07e2c72b8cd3e6e0181d987632ea5745c8954843c3ef1bf"
TRANSACTION = "transaction_timeout"
STATEMENT = "statement_timeout"
IDLE = "idle_in_transaction_session_timeout"


def scope(version, key, predicate="default"):
    return Scope("documentation", "PostgreSQL", f"{key}.{predicate}", version)


def source(version, lines):
    return f"https://github.com/postgres/postgres/blob/{RELEASES[version]}/doc/src/sgml/config.sgml#{lines}"


def setting_record(version, name, tag, lines):
    summary = f"PostgreSQL {version}: the documented default for {name} is 0 milliseconds, disabling the timeout."
    return Record(f"pg{version[:2]}-{tag}-default", scope(version, name), 0, "milliseconds",
                  summary, source(version, lines))


T17 = setting_record("17.0", TRANSACTION, "transaction", "L9368-L9382")
S17 = setting_record("17.0", STATEMENT, "statement", "L9332-L9346")
I17 = setting_record("17.0", IDLE, "idle", "L9441-L9454")
S16 = setting_record("16.0", STATEMENT, "statement", "L9118-L9132")
I16 = setting_record("16.0", IDLE, "idle", "L9191-L9204")
X17 = Record("pg17-transaction-exception", scope("17.0", TRANSACTION, "prepared_exception"),
             "excluded", "applicability",
             "PostgreSQL 17.0 transaction_timeout does not apply to a prepared transaction.",
             source("17.0", "L9396-L9400"))

T17_QUERY = Intent(scope("17.0", TRANSACTION), "PostgreSQL 17.0 transaction_timeout default")
S17_QUERY = Intent(scope("17.0", STATEMENT), "PostgreSQL 17.0 statement_timeout default")
T16_QUERY = Intent(scope("16.0", TRANSACTION), "PostgreSQL 16.0 transaction_timeout default")

# No externally supplied paths, catalogs, or queries enter this local experiment.
# Evidence removal changes the catalog, not the 17.0 question or intended scope.
CASES = {
    "pg17-transaction": (T17_QUERY, (T17, S17, I17)),
    "pg17-statement": (S17_QUERY, (T17, S17, I17)),
    "pg17-neighbors-only": (T17_QUERY, (S17, I17)),
    "pg16-neighbors-only": (T16_QUERY, (S16, I16)),
    "pg17-exception-only": (T17_QUERY, (X17,)),
}


def load_oracle():
    data = (HERE / "oracle.json").read_bytes()
    if digest(data) != ORACLE_SHA256:
        raise ValueError("frozen attribution oracle was modified")
    return json.loads(data)


def run_case(name):
    intent, records = CASES[name]

    class TransferAgent(DocumentAgent):
        _intents = MappingProxyType({name: intent})
        _records = records

        def _citation_source(self, owner):
            # The synthetic span is not another upstream locator fragment.
            return owner.source_url

    agent = TransferAgent()
    result = agent.answer(name)
    cites = result["citations"]
    contract = {key: result[key] for key in ("status", "reason", "retrieval_attempts",
                                            "ranking_attempts", "answer")}
    contract["citation"] = (
        {key: cites[0][key] for key in ("chunk_id", "source")}
        if len(cites) == 1 else None
    )
    expected = load_oracle()["cases"][name]
    if (contract != expected or len(cites) != int(expected["citation"] is not None)
            or result["model_calls"] != 0
            or (result["answer"] is not None and type(result["answer"]["value"]) is not int)):
        raise ValueError(f"{name} failed frozen type, scope, locator, or stop oracle")
    # A diagnostic probe only. Count it separately from normal agent dispatch.
    # This proves each negative is textually retrievable, not a trivial lexical zero.
    if expected["status"] == "stopped":
        diagnostic = [hit.chunk.id for hit in agent._index.bm25.search(intent.query)]
        if not diagnostic:
            raise ValueError(f"{name} has no lexical decoy in independent unscoped probe")
    else:
        diagnostic = []
    return {"case": name, "catalog_locators": {r.chunk_id: r.source for r in records},
            "result": result, "unscoped_diagnostic_hits": diagnostic}


def replay():
    rows = [run_case(name) for name in CASES]
    expected = load_oracle()["cases"]
    return {
        "model_calls": sum(r["result"]["model_calls"] for r in rows),
        "supported_positive_plans": sum(r["result"]["status"] == "answered" and expected[r["case"]]["status"] == "answered" for r in rows),
        "accepted_negative_plans": sum(r["result"]["status"] == "answered" and expected[r["case"]]["status"] == "stopped" for r in rows),
        "no_matching_scope_stops": sum(r["result"]["reason"] == "no_matching_scope" for r in rows),
        "agent_retrieval_attempts": sum(r["result"]["retrieval_attempts"] for r in rows),
        "agent_ranking_attempts": sum(r["result"]["ranking_attempts"] for r in rows),
        "separate_unscoped_diagnostic_passes": sum(bool(r["unscoped_diagnostic_hits"]) for r in rows),
        "oracle_sha256": ORACLE_SHA256,
        "rows": rows,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--check", action="store_true")
    action.add_argument("--case", choices=tuple(CASES))
    args = parser.parse_args()
    rendered = canonical_json(run_case(args.case) if args.case else replay())
    if args.check:
        if (HERE / "report.json").read_bytes() != rendered.encode("utf-8"):
            raise ValueError("recorded PostgreSQL transfer transcript changed")
        print("Five PostgreSQL Agent cases match the offline transcript.")
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
