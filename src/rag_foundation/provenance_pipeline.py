"""Opt-in scoped retrieval with source locators separate from local chunk spans."""

import argparse
from pathlib import Path

from .corpus import canonical_json
from .generation import LocalGenerator, strict_json
from .scope_gate import Scope
from .scoped_pipeline import ClaimIndex, ScopedGenerationPipeline


def render_provenance(chunk):
    """Treat nonempty upstream fragments as opaque; never append a second one."""
    base, separator, fragment = chunk.source_url.partition("#")
    if separator and fragment:
        locator = chunk.source_url
        kind = "upstream_fragment"
    else:
        locator = f"{base}#L{chunk.start_line}-L{chunk.end_line}"
        kind = "local_line_range"
    return {
        "source_url": chunk.source_url,
        "locator": locator,
        "locator_kind": kind,
        "local_span": {
            "start_char": chunk.start_char,
            "end_char": chunk.end_char,
            "start_line": chunk.start_line,
            "end_line": chunk.end_line,
        },
    }


class ProvenancePipeline:
    """New opt-in public API; historic serializers and frozen receipts unchanged.

    Catalog URLs are supplied by the operator, not the model. This renderer does
    not fetch, authenticate or establish semantic support for a source.
    """

    def __init__(self, index, generator=None):
        if not isinstance(index, ClaimIndex):
            raise ValueError("an index-owned ClaimIndex is required")
        self._chunks = {chunk.id: chunk for chunk in index.chunks}
        self._pipeline = ScopedGenerationPipeline(index, _RenderedGenerator(self, generator)
                                                  if generator is not None else None)

    def _render_hit(self, hit):
        evidence = render_provenance(self._chunks[hit["chunk_id"]])
        return {**hit, "citation": evidence["locator"], "provenance": evidence}

    def answer(self, query, scope, k=3, context_characters=12000, *, scope_gate=False, scan_limit=128):
        outcome = self._pipeline.answer(query, scope, k, context_characters,
                                        scope_gate=scope_gate, scan_limit=scan_limit)
        ranking = outcome["ranking"]
        if ranking is not None:
            ranking = {**ranking, "ranked_hits": [self._render_hit(hit) for hit in ranking["ranked_hits"]]}
        context = [self._render_hit(hit) for hit in outcome["context"]]
        citations = []
        if outcome["status"] == "answered" and outcome["generator_called"]:
            ids = outcome["generation"].get("citation_ids")
            by_id = {hit["chunk_id"]: hit["provenance"] for hit in context}
            if (type(ids) is not list or not ids or
                    any(type(cid) is not str or cid not in by_id for cid in ids) or
                    len(set(ids)) != len(ids)):
                raise ValueError("generator citation IDs must be unique members of the packed context")
            citations = [{"chunk_id": cid, **by_id[cid]} for cid in ids]
        return {**outcome, "ranking": ranking, "context": context, "citations": citations}


class _RenderedGenerator:
    def __init__(self, renderer, generator):
        self.renderer, self.generator = renderer, generator

    def generate(self, query, context):
        return self.generator.generate(query, [self.renderer._render_hit(hit) for hit in context])


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--chunks", type=Path, required=True, help="operator-owned chunk JSONL")
    cli.add_argument("--catalog", type=Path, required=True, help="operator-owned reviewed catalog JSON")
    cli.add_argument("--request", type=Path, required=True, help="query/scope only")
    cli.add_argument("--scope-gate", action="store_true", help="require typed evidence scope before ranking")
    cli.add_argument("-k", type=int, default=3)
    cli.add_argument("--context-characters", type=int, default=12000)
    cli.add_argument("--scan-limit", type=int, default=128)
    cli.add_argument("--endpoint", help="explicit loopback model server; otherwise offline")
    args = cli.parse_args()
    if args.request.stat().st_size > 10000:
        raise ValueError("request exceeds byte bound")
    request = strict_json(args.request.read_text(encoding="utf-8"))
    if not isinstance(request, dict) or set(request) != {"query", "scope"}:
        raise ValueError("request requires query/scope only; records are index-owned")
    index = ClaimIndex.from_files(args.chunks, args.catalog)
    model = LocalGenerator(args.endpoint) if args.endpoint else None
    result = ProvenancePipeline(index, model).answer(
        request["query"], Scope.from_dict(request["scope"]), args.k, args.context_characters,
        scope_gate=args.scope_gate, scan_limit=args.scan_limit)
    print(canonical_json(result), end="")


if __name__ == "__main__":
    main()
