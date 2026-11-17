"""Model-free schema-shape regression. Not a native GBNF acceptance checker."""
import hashlib
import json
from pathlib import Path
from protocol import shape_accepts, strict_json, validate_answer

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def python_accepts(value, ids):
    try:
        validate_answer(value, ids)
        return True
    except (ValueError, TypeError, UnicodeError):
        return False


def preflight():
    historical = []
    for path in sorted((REPO / 'experiments/numbered-spans-v1/recorded').glob('*.result.json')):
        result = strict_json(path.read_text())
        generation = result['generator']
        if generation is None:
            continue
        value = strict_json(strict_json(generation['raw_response'])['choices'][0]['message']['content'])
        ids = [c['chunk_id'] for c in result['selector']['selected_context']]
        historical.append({'source_file': path.relative_to(REPO).as_posix(),
            'source_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'legacy_schema_shape': shape_accepts(value, ids, 'legacy'),
            'branched_schema_shape': shape_accepts(value, ids, 'branched'),
            'python_contract': python_accepts(value, ids)})
    fixtures = [
        ('cited_answer', {'answer': 'invented example', 'citations': ['1'], 'abstain': False}, True, True),
        ('empty_refusal', {'answer': '', 'citations': [], 'abstain': True}, True, True),
        ('missing_citation', {'answer': 'invented example', 'citations': [], 'abstain': False}, False, False),
        ('refusal_with_text', {'answer': 'unknown', 'citations': [], 'abstain': True}, False, False),
        ('refusal_with_citation', {'answer': '', 'citations': ['1'], 'abstain': True}, False, False),
        ('unknown_id', {'answer': 'a', 'citations': ['9'], 'abstain': False}, False, False),
        ('whitespace_answer', {'answer': ' ', 'citations': ['1'], 'abstain': False}, True, False),
        ('duplicate_citation', {'answer': 'a', 'citations': ['1', '1'], 'abstain': False}, True, False),
        ('empty_answer', {'answer': '', 'citations': ['1'], 'abstain': False}, False, False),
    ]
    rows = []
    for name, value, expected_shape, expected_python in fixtures:
        shape, contract = shape_accepts(value, ['1'], 'branched'), python_accepts(value, ['1'])
        if (shape, contract) != (expected_shape, expected_python):
            raise ValueError('preflight mismatch: ' + name)
        rows.append({'id': name, 'value': value, 'branched_schema_shape': shape, 'python_contract': contract})
    return {'scope': 'Offline original schema-shape checker plus existing Python validator; not native grammar compilation/validation or new model inference.',
            'native_compiler': 'Not executed. Pinned official tree has C++ converter only; release lacks gbnf-validator. Server behavior is tested separately by the live run.',
            'historical_regressions': historical, 'fresh_shape_fixtures': rows}


if __name__ == '__main__':
    print(json.dumps(preflight(), ensure_ascii=False, indent=2))
