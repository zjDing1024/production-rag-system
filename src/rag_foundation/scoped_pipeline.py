"""Opt-in index-owned metadata and reviewed single-value preflight before BM25.

Catalog completeness and claim semantics are operator assertions, not NLP or
security guarantees. Old RetrievalService/GenerationPipeline behavior is unchanged.
"""
import argparse
from dataclasses import asdict, dataclass
from pathlib import Path
from types import MappingProxyType

from .corpus import Chunk, canonical_json, digest, read_chunks
from .generation import LocalGenerator, strict_json
from .retrieval import BM25
from .scope_gate import Scope

MAX_CHUNKS = 2048
MAX_INDEX_CHARACTERS = 2_000_000
MAX_FILE_BYTES = 8_000_000


def bounded_int(value, label, maximum):
    if type(value) is not int or not 1 <= value <= maximum:
        raise ValueError(f'{label} must be an integer in 1..{maximum}')
    return value


def chunks_fingerprint(chunks):
    return digest(canonical_json([asdict(c) for c in chunks]).encode('utf-8'))


@dataclass(frozen=True)
class ReviewedValue:
    value_type: str
    unit: str
    value: object
    start_char: int
    end_char: int
    quote: str

    @classmethod
    def bind(cls, row, chunk):
        if row is None:
            return None  # Explicitly missing/unreviewed, not a null claim value.
        keys = {'reviewed', 'chunk_text_sha256', 'value_type', 'unit', 'value',
                'start_char', 'end_char', 'quote'}
        if not isinstance(row, dict) or set(row) != keys or row['reviewed'] is not True:
            raise ValueError('claim must be null or a complete reviewed single-value claim')
        if row['chunk_text_sha256'] != digest(chunk.text.encode('utf-8')):
            raise ValueError('reviewed claim text hash mismatch')
        start, end, quote = row['start_char'], row['end_char'], row['quote']
        if (type(start) is not int or type(end) is not int or not 0 <= start < end <= len(chunk.text)
                or not isinstance(quote, str) or chunk.text[start:end] != quote):
            raise ValueError('reviewed claim source span mismatch')
        kind, unit, value = row['value_type'], row['unit'], row['value']
        if not isinstance(unit, str) or not unit or len(unit) > 64 or not unit.isascii() or not all(c.isalnum() or c in '_-/' for c in unit):
            raise ValueError('unit must be a bounded canonical ASCII label')
        if kind == 'integer':
            valid = type(value) is int and abs(value) <= 10**12
        elif kind == 'string':
            valid = isinstance(value, str) and 0 < len(value) <= 512
            if valid:
                value.encode('utf-8')
        elif kind == 'null':
            valid = value is None
        else:
            valid = False
        if not valid:
            raise ValueError('invalid canonical single value')
        return cls(kind, unit, value, start, end, quote)


class EligibleBM25(BM25):
    """Preserve the frozen scorer; filter full bounded results before request top-k.

    Scoring all chunks is intentional: no corpus statistic is recomputed on an
    eligible subset. This is a correctness-first wrapper, not an optimized index.
    """
    def search(self, query, k=5, *, eligible_ids=None):
        bounded_int(k, 'k', MAX_CHUNKS)
        if eligible_ids is None:
            return super().search(query, k)
        if not isinstance(eligible_ids, (set, frozenset)) or any(not isinstance(cid, str) for cid in eligible_ids):
            raise ValueError('eligible_ids must be a set of indexed string IDs')
        if not eligible_ids <= {c.id for c in self.chunks}:
            raise ValueError('unknown eligible ID')
        all_hits = super().search(query, max(1, len(self.chunks)))
        return [h for h in all_hits if h.chunk.id in eligible_ids][:k]


class ClaimIndex:
    """One fixed chunk corpus and an operator-owned, fingerprint-bound catalog.

    The request cannot provide candidate records or replace catalog claims.
    Missing entry/scope or complete=false conservatively makes all scoped reads
    unknown, because unknown scope might hide an in-scope contradiction.
    """
    def __init__(self, chunks, catalog):
        if not isinstance(chunks, (list, tuple)) or not 1 <= len(chunks) <= MAX_CHUNKS:
            raise ValueError('index requires 1..2048 chunks')
        if any(not isinstance(c, Chunk) or not c.id or not isinstance(c.text, str) or not c.text.strip() for c in chunks):
            raise ValueError('invalid index chunk')
        if sum(len(c.text) for c in chunks) > MAX_INDEX_CHARACTERS:
            raise ValueError('index character limit exceeded')
        if not isinstance(catalog, dict) or set(catalog) != {'schema_version', 'complete', 'chunks_sha256', 'entries'}:
            raise ValueError('invalid claim catalog fields')
        if type(catalog['schema_version']) is not int or catalog['schema_version'] != 1 or type(catalog['complete']) is not bool:
            raise ValueError('invalid claim catalog version or completeness')
        self.chunks = tuple(chunks)
        self.fingerprint = chunks_fingerprint(self.chunks)
        if catalog['chunks_sha256'] != self.fingerprint:
            raise ValueError('catalog/index fingerprint mismatch')
        self.bm25 = EligibleBM25(list(self.chunks))
        by_id = {c.id: c for c in self.chunks}
        if not isinstance(catalog['entries'], list) or len(catalog['entries']) > len(chunks):
            raise ValueError('invalid catalog entry count')
        scopes, claims = {}, {}
        for entry in catalog['entries']:
            if not isinstance(entry, dict) or set(entry) != {'chunk_id', 'scope', 'claim'}:
                raise ValueError('invalid catalog entry')
            cid = entry['chunk_id']
            if not isinstance(cid, str) or cid not in by_id or cid in scopes:
                raise ValueError('unknown or duplicate catalog ID')
            scopes[cid] = Scope.from_dict(entry['scope']) if entry['scope'] is not None else None
            claims[cid] = ReviewedValue.bind(entry['claim'], by_id[cid])
        self.scopes = MappingProxyType(scopes)
        self.claims = MappingProxyType(claims)
        self.unassigned_ids = tuple(c.id for c in chunks if scopes.get(c.id) is None)
        self.complete = catalog['complete']
        self.catalog_sha256 = digest(canonical_json(catalog).encode('utf-8'))

    @classmethod
    def from_files(cls, chunks_path, catalog_path):
        for path in (chunks_path, catalog_path):
            if path.stat().st_size > MAX_FILE_BYTES:
                raise ValueError('index file exceeds byte bound')
        return cls(read_chunks(chunks_path), strict_json(catalog_path.read_text(encoding='utf-8')))

    def assess(self, request, scan_limit=128):
        if not isinstance(request, Scope):
            raise ValueError('typed requested scope required')
        bounded_int(scan_limit, 'scan_limit', MAX_CHUNKS)
        ids = tuple(c.id for c in self.chunks if self.scopes.get(c.id) == request)
        result = {'status': 'unknown', 'reason': None, 'matched_ids': list(ids),
                  'matched_count': len(ids), 'reviewed_count': None, 'scope_scan_complete': False,
                  'unassigned_ids': list(self.unassigned_ids), 'distinct_value_count': None,
                  'trust_boundary': 'operator_reviewed_catalog', 'semantic_support': 'unverified'}
        if not self.complete or self.unassigned_ids:
            result['reason'] = 'catalog_incomplete'
        elif len(ids) > scan_limit:
            result['reason'] = 'scope_scan_limit'
        else:
            values = [self.claims[cid] for cid in ids if self.claims[cid] is not None]
            result.update(scope_scan_complete=True, reviewed_count=len(values))
            if not ids:
                result.update(status='no_match', reason='no_matching_scope')
            elif len(values) != len(ids):
                result['reason'] = 'missing_reviewed_claim'
            elif len({(v.value_type, v.unit) for v in values}) != 1:
                result['reason'] = 'incomparable_claims'
            else:
                distinct = len({v.value for v in values})
                result.update(distinct_value_count=distinct,
                              status='conflict' if distinct > 1 else 'consistent',
                              reason='reviewed_value_conflict' if distinct > 1 else 'reviewed_values_agree')
        return result


class ScopedGenerationPipeline:
    """Real BM25 -> context budget -> optional generator; scope checks opt in."""
    def __init__(self, index, generator=None):
        if not isinstance(index, ClaimIndex):
            raise ValueError('an index-owned ClaimIndex is required')
        self.index, self.generator = index, generator

    def answer(self, query, scope, k=3, context_characters=12000, *, scope_gate=False, scan_limit=128):
        if not isinstance(query, str) or not query.strip() or len(query) > 2000:
            raise ValueError('query must contain 1..2000 characters')
        query.encode('utf-8')
        if not isinstance(scope, Scope) or type(scope_gate) is not bool:
            raise ValueError('typed scope and boolean scope_gate required')
        bounded_int(k, 'k', 3)
        bounded_int(context_characters, 'context_characters', 12000)
        bounded_int(scan_limit, 'scan_limit', MAX_CHUNKS)
        result = {'mode': 'indexed-scope-opt-in', 'query': query, 'requested_scope': asdict(scope),
                  'scope_gate': scope_gate, 'status': 'not_run', 'reason': None,
                  'semantic_support': 'unverified', 'index_sha256': self.index.fingerprint,
                  'catalog_sha256': self.index.catalog_sha256, 'preflight': None,
                  'ranking': None, 'context': [], 'generation': None, 'generator_called': False,
                  'limits': {'k': k, 'context_characters': context_characters, 'scan_limit': scan_limit}}
        eligible = None
        if scope_gate:
            preflight = self.index.assess(scope, scan_limit)
            result['preflight'] = preflight
            if preflight['status'] != 'consistent':
                result['reason'] = preflight['reason']
                return result
            eligible = frozenset(preflight['matched_ids'])
        # Rank over the original full index. Eligibility is applied before top-k;
        # all ranked candidates are counted here for auditable omissions.
        hits = self.index.bm25.search(query, len(self.index.chunks), eligible_ids=eligible)
        ranked = hits[:k]
        result['ranking'] = {'statistics': 'full_index', 'corpus_count': len(self.index.chunks),
            'eligible_count': len(eligible) if eligible is not None else len(self.index.chunks),
            'lexical_candidate_count': len(hits), 'zero_overlap_count': (len(eligible) if eligible is not None else len(self.index.chunks)) - len(hits),
            'top_k_omitted_ids': [h.chunk.id for h in hits[k:]],
            'ranked_hits': [h.to_dict() for h in ranked], 'budget_omitted_ids': []}
        if not ranked:
            result['reason'] = 'no_lexical_candidates'
            return result
        size = 0
        for pos, hit in enumerate(ranked):
            if size + len(hit.chunk.text) > context_characters:
                result['ranking']['budget_omitted_ids'] = [h.chunk.id for h in ranked[pos:]]
                break
            result['context'].append(hit.to_dict())
            size += len(hit.chunk.text)
        if not result['context']:
            result['reason'] = 'context_budget_exhausted'
            return result
        if self.generator is None:
            result.update(status='planned', reason='generator_not_requested')
            return result
        result['generator_called'] = True
        generated = self.generator.generate(query, result['context'])
        result.update(status=generated['status'], reason=generated['reason'], generation=generated)
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--chunks', type=Path, required=True, help='operator-owned chunk JSONL')
    parser.add_argument('--catalog', type=Path, required=True, help='operator-owned reviewed catalog JSON')
    parser.add_argument('--request', type=Path, required=True, help='query/scope only, no supplied records')
    parser.add_argument('--scope-gate', action='store_true')
    parser.add_argument('-k', type=int, default=3)
    parser.add_argument('--context-characters', type=int, default=12000)
    parser.add_argument('--scan-limit', type=int, default=128)
    parser.add_argument('--endpoint', help='explicit loopback model endpoint; omitted is offline plan')
    args = parser.parse_args()
    if args.request.stat().st_size > 10000:
        raise ValueError('request exceeds byte bound')
    request = strict_json(args.request.read_text(encoding='utf-8'))
    if not isinstance(request, dict) or set(request) != {'query', 'scope'}:
        raise ValueError('request requires query/scope only; records are index-owned')
    index = ClaimIndex.from_files(args.chunks, args.catalog)
    generator = LocalGenerator(args.endpoint) if args.endpoint else None
    result = ScopedGenerationPipeline(index, generator).answer(request['query'], Scope.from_dict(request['scope']),
        args.k, args.context_characters, scope_gate=args.scope_gate, scan_limit=args.scan_limit)
    print(canonical_json(result), end='')


if __name__ == '__main__':
    main()
