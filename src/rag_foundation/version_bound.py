"""Opt-in literal release consistency check for a documentation request."""
import argparse
from pathlib import Path
import re

from .corpus import canonical_json
from .generation import LocalGenerator, strict_json
from .scope_gate import Scope
from .scoped_pipeline import ClaimIndex, ScopedGenerationPipeline, bounded_int, MAX_CHUNKS

# This grammar detects ASCII dotted numeric tokens, not natural-language intent or
# SemVer ranges. Retaining unsupported suffixes prevents treating 5.1.0-rc.1 as 5.1.0.
_DOTTED = re.compile(r"(?<![A-Za-z0-9_.])v?[0-9]+(?:\.[0-9]+)+(?:\.?[A-Za-z0-9_+-]+(?:\.[A-Za-z0-9_+-]+)*)?")
_RELEASE = re.compile(r"(?:0|[1-9][0-9]*)(?:\.(?:0|[1-9][0-9]*)){2}")


def check_version(query, scope):
    """Compare one explicit literal release token to an exact documentation scope."""
    if not isinstance(query, str) or not query.strip() or len(query) > 2000:
        raise ValueError('query must contain 1..2000 characters')
    query.encode('utf-8')
    if not isinstance(scope, Scope):
        raise ValueError('typed scope required')
    observations = [
        {'token': m.group(), 'start': m.start(), 'end': m.end()}
        for m in _DOTTED.finditer(query)
    ]
    result = {'status': 'not_bound', 'reason': None,
              'observations': observations, 'scope_version': scope.version,
              'semantic_support': 'unverified'}
    if scope.kind != 'documentation' or not _RELEASE.fullmatch(scope.version):
        result['reason'] = 'unsupported_documentation_scope'
    elif not observations:
        result['reason'] = 'no_explicit_release'
    elif len(observations) != 1:
        result['reason'] = 'ambiguous_release_mentions'
    else:
        candidate = observations[0]['token'].removeprefix('v')
        prefix = query[:observations[0]['start']].rstrip()
        suffix = query[observations[0]['end']:]
        symbolic = (prefix.endswith(tuple('<>=~^≤≥≦≧≠≈'))
                    or suffix.startswith('*') or re.match(r'\.+[A-Za-z0-9_*+-]', suffix))
        if not _RELEASE.fullmatch(candidate) or symbolic:
            result['reason'] = 'unsupported_release_token'
        elif candidate != scope.version:
            result['reason'] = 'question_scope_release_mismatch'
        else:
            result.update(status='bound', reason='literal_release_matches')
    return result


def answer_with_version_binding(pipeline, query, scope, k=3, context_characters=12000, *, scan_limit=128):
    """Gate before the scoped pipeline, preserving the query verbatim on success."""
    if not isinstance(pipeline, ScopedGenerationPipeline):
        raise ValueError('scoped generation pipeline required')
    bounded_int(k, 'k', 3)
    bounded_int(context_characters, 'context_characters', 12000)
    bounded_int(scan_limit, 'scan_limit', MAX_CHUNKS)
    binding = check_version(query, scope)
    outcome = None
    if binding['status'] == 'bound':
        outcome = pipeline.answer(query, scope, k, context_characters,
                                  scope_gate=True, scan_limit=scan_limit)
    return {'mode': 'explicit-version-binding-opt-in', 'query': query,
            'binding': binding, 'pipeline': outcome,
            'status': outcome['status'] if outcome is not None else 'not_run',
            'reason': outcome['reason'] if outcome is not None else binding['reason'],
            'generator_called': outcome['generator_called'] if outcome is not None else False,
            'semantic_support': 'unverified'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--chunks', type=Path, required=True)
    parser.add_argument('--catalog', type=Path, required=True)
    parser.add_argument('--request', type=Path, required=True)
    parser.add_argument('-k', type=int, default=3)
    parser.add_argument('--endpoint', help='explicit loopback model endpoint; omit to plan offline')
    args = parser.parse_args()
    if args.request.stat().st_size > 10_000:
        raise ValueError('request exceeds byte bound')
    request = strict_json(args.request.read_text(encoding='utf-8'))
    if not isinstance(request, dict) or set(request) != {'query', 'scope'}:
        raise ValueError('request requires query/scope only')
    scope = Scope.from_dict(request['scope'])
    index = ClaimIndex.from_files(args.chunks, args.catalog)
    generator = LocalGenerator(args.endpoint) if args.endpoint else None
    pipeline = ScopedGenerationPipeline(index, generator)
    result = answer_with_version_binding(pipeline, request['query'], scope, args.k)
    print(canonical_json(result), end='')


if __name__ == '__main__':
    main()
