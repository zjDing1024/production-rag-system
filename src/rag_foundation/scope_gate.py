"""Opt-in typed metadata matching. It does not infer scope or verify semantic support."""
import argparse
from dataclasses import asdict, dataclass
from datetime import datetime
import json
from pathlib import Path
import re
from .generation import LocalGenerator, strict_json

SCOPE_FIELDS = {'kind', 'subject', 'key', 'version', 'observed_at'}
RECORD_FIELDS = {'record_id', 'scope', 'text', 'citation'}


def _text(value, name, limit):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f'{name} must be nonempty text of at most {limit} characters')
    value.encode('utf-8')
    if any(ord(c) < 32 for c in value):
        raise ValueError(name + ' contains a control character')
    return value


@dataclass(frozen=True)
class Scope:
    kind: str
    subject: str
    key: str
    version: str | None = None
    observed_at: str | None = None

    def __post_init__(self):
        if self.kind not in ('documentation', 'runtime'):
            raise ValueError('kind must be documentation or runtime')
        _text(self.subject, 'subject', 128)
        _text(self.key, 'key', 128)
        if self.kind == 'documentation':
            _text(self.version, 'version', 64)
            if self.observed_at is not None:
                raise ValueError('documentation scope has version, not observed_at')
        else:
            if self.version is not None or not isinstance(self.observed_at, str):
                raise ValueError('runtime scope has observed_at, not version')
            if not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z', self.observed_at):
                raise ValueError('observed_at must be a canonical UTC second timestamp')
            datetime.strptime(self.observed_at, '%Y-%m-%dT%H:%M:%SZ')

    @classmethod
    def from_dict(cls, value):
        if not isinstance(value, dict) or set(value) != SCOPE_FIELDS:
            raise ValueError('scope requires exactly kind, subject, key, version, observed_at')
        return cls(**value)


@dataclass(frozen=True)
class EvidenceRecord:
    record_id: str
    scope: Scope
    text: str
    citation: str

    def __post_init__(self):
        if not isinstance(self.record_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', self.record_id):
            raise ValueError('record_id must be a bounded opaque ASCII ID')
        if not isinstance(self.scope, Scope):
            raise ValueError('record scope must be typed')
        if not isinstance(self.text, str) or not self.text.strip() or len(self.text) > 4000:
            raise ValueError('record text must contain 1..4000 characters')
        self.text.encode('utf-8')
        _text(self.citation, 'citation', 2048)
        if not self.citation.startswith(('https://', 'synthetic://')):
            raise ValueError('citation must be an HTTPS or explicitly synthetic identifier')

    @classmethod
    def from_dict(cls, value):
        if not isinstance(value, dict) or set(value) != RECORD_FIELDS:
            raise ValueError('record requires exactly record_id, scope, text, citation')
        return cls(value['record_id'], Scope.from_dict(value['scope']), value['text'], value['citation'])

    def context(self):
        return {'chunk_id': self.record_id, 'text': self.text, 'citation': self.citation}


def validate_records(records):
    if not isinstance(records, (list, tuple)) or len(records) > 12:
        raise ValueError('expected at most 12 records')
    if any(not isinstance(r, EvidenceRecord) for r in records):
        raise ValueError('records must be typed EvidenceRecord instances')
    if len({r.record_id for r in records}) != len(records):
        raise ValueError('record IDs must be unique')
    if sum(len(r.text) for r in records) > 12000:
        raise ValueError('record text budget exceeds 12000 characters')


def select_scope(request, records):
    """Exact metadata comparison; no text entailment check or natural-query parsing."""
    if not isinstance(request, Scope):
        raise ValueError('request must be a typed Scope')
    validate_records(records)
    matches, rejected = [], []
    fields = ('kind', 'subject', 'key', 'version', 'observed_at')
    for record in records:
        reasons = [field + '_mismatch' for field in fields
                   if getattr(request, field) != getattr(record.scope, field)]
        if reasons:
            rejected.append({'record_id': record.record_id, 'reason_codes': reasons})
        else:
            matches.append(record)
    return {'status': 'matched' if matches else 'no_match',
            'matched_ids': [r.record_id for r in matches], 'rejected': rejected,
            'semantic_support': 'unverified', 'trust_boundary': 'caller_supplied_metadata'}, matches


def plan(query, scope, records, gate_enabled=False):
    _text(query, 'query', 2000)
    if not isinstance(scope, Scope) or type(gate_enabled) is not bool:
        raise ValueError('typed scope and boolean gate_enabled required')
    validate_records(records)
    decision, chosen = select_scope(scope, records) if gate_enabled else (None, list(records))
    return {'mode': 'typed-scope-opt-in', 'gate_enabled': gate_enabled,
            'requested_scope': asdict(scope), 'supplied_ids': [r.record_id for r in records],
            'gate': decision, 'context': [r.context() for r in chosen],
            'semantic_support': 'unverified', 'generator_called': False,
            'status': 'planned' if chosen else 'not_run',
            'reason': 'generator_not_requested' if chosen else 'no_matching_scope' if gate_enabled else 'no_supplied_records'}


def answer(query, scope, records, generator, gate_enabled=False):
    result = plan(query, scope, records, gate_enabled)
    if not result['context']:
        result['generation'] = None
        return result
    generated = generator.generate(query, result['context'])
    result.update(status=generated['status'], reason=generated['reason'], generator_called=True,
                  generation=generated)
    return result


def parse_input(value):
    if not isinstance(value, dict) or set(value) != {'query', 'scope', 'records'}:
        raise ValueError('input requires exactly query, scope, records')
    if not isinstance(value['records'], list):
        raise ValueError('records must be an array')
    return value['query'], Scope.from_dict(value['scope']), [EvidenceRecord.from_dict(r) for r in value['records']]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path, help='JSON with query, scope and records')
    parser.add_argument('--gate', action='store_true', help='opt in to exact typed scope filtering')
    parser.add_argument('--endpoint', help='explicit loopback model endpoint; omitted means offline plan only')
    args = parser.parse_args()
    if args.input.stat().st_size > 100000:
        raise ValueError('input file exceeds 100000 bytes')
    query, scope, records = parse_input(strict_json(args.input.read_text(encoding='utf-8')))
    result = (answer(query, scope, records, LocalGenerator(args.endpoint), args.gate) if args.endpoint
              else plan(query, scope, records, args.gate))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
