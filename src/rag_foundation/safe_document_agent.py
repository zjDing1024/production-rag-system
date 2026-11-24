"""Opt-in, finite-policy read-only document Q&A over a bundled reviewed catalog."""

import argparse
from dataclasses import asdict, dataclass
from types import MappingProxyType

from .corpus import Chunk, canonical_json, digest
from .scope_gate import Scope
from .scoped_pipeline import ClaimIndex, ScopedGenerationPipeline, bounded_int, chunks_fingerprint

MAX_RETRIEVALS = 2
MAX_CHUNKS = 16
MAX_CORPUS_CHARACTERS = 4096
MAX_CONTEXT_CHARACTERS = 512
MAX_QUERY_CHARACTERS = 128


@dataclass(frozen=True)
class Intent:
    scope: Scope
    query: str
    fallback: str | None = None


@dataclass(frozen=True)
class Record:
    chunk_id: str
    scope: Scope
    value: str | int
    unit: str
    summary: str
    source: str
    reviewed: bool = True


_OLD = Scope("documentation", "Express", "query parser.default", "4.21.2")
_NEW = Scope("documentation", "Express", "query parser.default", "5.1.0")
_COLOR = Scope("documentation", "CPython", "ArgumentParser.color.default", "3.14.0")
_CONFLICT = Scope("documentation", "DemoBox", "timeout.default", "1.0.0")
_MISSING = Scope("documentation", "DemoBox", "retry_limit.default", "1.0.0")
_PARTIAL = Scope("documentation", "DemoBox", "queue_size.default", "1.0.0")

INTENTS = MappingProxyType({
    "express-4-default": Intent(_OLD, "Express query parser default"),
    "express-5-default": Intent(_NEW, "Express query parser default"),
    "cpython-color-retry": Intent(_COLOR, "颜色默认值", "ArgumentParser color default"),
    "demo-timeout-conflict": Intent(_CONFLICT, "DemoBox timeout", "timeout default"),
    "demo-retries-missing": Intent(_MISSING, "DemoBox retry limit"),
    "demo-queue-unreviewed": Intent(_PARTIAL, "DemoBox queue size"),
})

RECORDS = (
    Record("express-4", _OLD, "extended", "parser_mode",
           "Express 4.21.2 sets the query parser default to extended.",
           "https://github.com/expressjs/express/blob/1faf228935aa0a13111f92c28ee795be64ce3f0f/lib/application.js#L80-L86"),
    Record("express-5", _NEW, "simple", "parser_mode",
           "Express 5.1.0 sets the query parser default to simple.",
           "https://github.com/expressjs/express/blob/cd7d4397c398a3f3ecadeaf9ef6ac1377bd414c4/lib/application.js#L93-L100"),
    Record("cpython-color", _COLOR, "True", "canonical_boolean_string",
           "In CPython 3.14.0, the ArgumentParser color parameter defaults to True.",
           "https://github.com/python/cpython/blob/ebf955df7a89ed0c7968f79faec1de49f61ed7cb/Lib/argparse.py#L1877-L1881"),
    Record("demo-timeout-a", _CONFLICT, 5, "seconds",
           "DemoBox 1.0.0 timeout default is 5 seconds.", "synthetic://demo/timeout-a"),
    Record("demo-timeout-b", _CONFLICT, 8, "seconds",
           "Illustrative limit of eight seconds; reviewed documented value is 8.",
           "synthetic://demo/timeout-b"),
    Record("demo-queue", _PARTIAL, 16, "entries",
           "Draft example queue size of 16; no reviewed default is available.",
           "synthetic://demo/queue-draft", reviewed=False),
)


def build_index():
    if len(RECORDS) > MAX_CHUNKS or sum(len(record.summary) for record in RECORDS) > MAX_CORPUS_CHARACTERS:
        raise ValueError("offline catalog exceeds its bound")
    chunks, entries = [], []
    for record in RECORDS:
        h = digest(record.summary.encode("utf-8"))
        cid = record.chunk_id
        chunks.append(Chunk(cid, cid, "Original reviewed summary", record.summary, record.source,
                            h, "MIT", 0, len(record.summary), 1, 1))
        entries.append({
            "chunk_id": cid, "scope": asdict(record.scope),
            "claim": None if not record.reviewed else {
                "reviewed": True, "value_type": "integer" if type(record.value) is int else "string",
                "unit": record.unit, "value": record.value, "quote": record.summary,
                "chunk_text_sha256": h, "start_char": 0, "end_char": len(record.summary),
            },
        })
    return ClaimIndex(chunks, {
        "schema_version": 1, "complete": True,
        "chunks_sha256": chunks_fingerprint(chunks), "entries": entries,
    })


class DocumentAgent:
    """No open-ended tools: resolve intent, inspect scope, retrieve, cite or stop."""

    def __init__(self):
        self._index = build_index()
        # This path always plans offline; there is no adapter injection or model API.
        self._retriever = ScopedGenerationPipeline(self._index)

    def answer(self, request_id, *, expected_scope=None, max_retrievals=2, context_characters=512):
        bounded_int(max_retrievals, "max_retrievals", MAX_RETRIEVALS)
        bounded_int(context_characters, "context_characters", MAX_CONTEXT_CHARACTERS)
        if not isinstance(request_id, str) or not (1 <= len(request_id) <= 80) or not request_id.isascii():
            raise ValueError("request_id must be a bounded ASCII string")
        if expected_scope is not None and not isinstance(expected_scope, Scope):
            raise ValueError("expected_scope must be a typed Scope")
        result = {
            "mode": "bounded_read_only_document_agent", "intent_id": request_id,
            "status": "stopped", "reason": None, "answer": None, "citations": [], "trace": [],
            "bound_scope": None, "retrieval_attempts": 0, "ranking_attempts": 0,
            "catalog": {"chunks": len(self._index.chunks), "sha256": self._index.catalog_sha256},
            "limits": {"retrievals": max_retrievals, "top_k": 1, "context_characters": context_characters},
            "model_calls": 0, "semantic_entailment_checked": False,
            "trust_boundary": "operator_reviewed_catalog_and_fixed_intent_map",
        }

        def stop(reason):
            result["reason"] = reason
            result["trace"].append({"event": "stop", "reason": reason})
            return result

        intent = INTENTS.get(request_id)
        if intent is None:
            return stop("unknown_intent")
        result["bound_scope"] = asdict(intent.scope)
        if expected_scope is not None and expected_scope != intent.scope:
            return stop("intent_scope_mismatch")
        result["trace"].append({"event": "scope_bound", "scope": asdict(intent.scope)})

        for step, query in enumerate(filter(None, (intent.query, intent.fallback)), 1):
            if step > max_retrievals:
                return stop("retrieval_budget_exhausted")
            if len(query) > MAX_QUERY_CHARACTERS:
                raise ValueError("configured query exceeds fixed catalog bound")
            result["retrieval_attempts"] += 1
            outcome = self._retriever.answer(query, intent.scope, k=1, context_characters=context_characters,
                                             scope_gate=True, scan_limit=MAX_CHUNKS)
            ranking = outcome["ranking"]
            result["ranking_attempts"] += int(ranking is not None)
            packed = outcome["context"]
            checked = outcome["preflight"]
            result["trace"].append({
                "event": "retrieve", "step": step, "strategy": "primary" if step == 1 else "reviewed_alias",
                "query": query, "reason": outcome["reason"],
                "scope_preflight": checked["reason"], "matched_ids": checked["matched_ids"],
                "lexical_hits": ranking["lexical_candidate_count"] if ranking is not None else None,
                "packed_ids": [hit["chunk_id"] for hit in packed],
            })
            if outcome["reason"] == "no_lexical_candidates" and step == 1 and intent.fallback is not None:
                continue  # One prewritten local alias, never an inferred or generated tool call.
            if outcome["status"] != "planned" or len(packed) != 1:
                return stop(outcome["reason"])
            hit, = packed
            cid = hit["chunk_id"]
            claim = self._index.claims.get(cid)
            # A valid ID is not enough: require its exact reviewed scope and span.
            if claim is None or self._index.scopes.get(cid) != intent.scope or cid not in checked["matched_ids"]:
                return stop("citation_scope_mismatch")
            owner = next(c for c in self._index.chunks if c.id == cid)
            if hit["citation"] != owner.citation or hit["text"] != owner.text:
                return stop("citation_provenance_mismatch")
            if owner.text[claim.start_char:claim.end_char] != claim.quote:
                return stop("citation_quote_mismatch")
            result.update(status="answered", reason="reviewed_claim_cited",
                          answer={"value": claim.value, "value_type": claim.value_type, "unit": claim.unit},
                          citations=[{"chunk_id": cid, "source": hit["citation"], "quote": claim.quote,
                                      "start_char": claim.start_char, "end_char": claim.end_char,
                                      "summary_sha256": digest(hit["text"].encode("utf-8"))}])
            result["trace"].append({"event": "cite", "chunk_id": cid})
            return result
        return stop("no_lexical_candidates")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("request", nargs="?", help="reviewed request ID")
    parser.add_argument("--expect-scope-of", choices=sorted(INTENTS), help="optional second reviewed scope, to test binding")
    parser.add_argument("--list", action="store_true", help="list only reviewed request IDs and scopes")
    parser.add_argument("--max-retrievals", type=int, default=MAX_RETRIEVALS)
    parser.add_argument("--context-characters", type=int, default=MAX_CONTEXT_CHARACTERS)
    args = parser.parse_args()
    if args.list == (args.request is not None) or (args.list and args.expect_scope_of):
        parser.error("choose one reviewed request, or --list")
    if args.list:
        result = {name: asdict(intent.scope) for name, intent in sorted(INTENTS.items())}
    else:
        expected = INTENTS[args.expect_scope_of].scope if args.expect_scope_of else None
        result = DocumentAgent().answer(args.request, expected_scope=expected, max_retrievals=args.max_retrievals,
                                        context_characters=args.context_characters)
    print(canonical_json(result), end="")


if __name__ == "__main__":
    main()
