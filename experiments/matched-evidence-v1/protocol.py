"""Opt-in experiment: unchanged numbered selector and answer-schema-only comparison."""
import copy
import http.client
import importlib.util
import json
from pathlib import Path
from unittest.mock import Mock, patch

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
spec = importlib.util.spec_from_file_location('frozen_span_protocol', REPO / 'experiments/numbered-spans-v1/mechanics.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
SpanSelector = module.SpanSelector
LocalGenerator = module.LocalGenerator
make_selector_payload = module.make_payload
from rag_foundation.generation import strict_json, validate_answer, response_schema

ARMS = ('legacy', 'branched')


def branch_schema(ids):
    """Whole object alternatives, not unsupported if/then or mixed properties+anyOf."""
    if (not isinstance(ids, list) or not ids or any(type(i) is not str or not i for i in ids)
            or len(set(ids)) != len(ids)):
        raise ValueError('expected unique nonempty citation IDs')
    return {'anyOf': [
        {'type': 'object', 'additionalProperties': False,
         'properties': {'answer': {'type': 'string', 'minLength': 1, 'maxLength': 4000},
                        'citations': {'type': 'array', 'items': {'type': 'string', 'enum': ids},
                                      'minItems': 1, 'maxItems': 3},
                        'abstain': {'const': False}},
         'required': ['answer', 'citations', 'abstain']},
        {'type': 'object', 'additionalProperties': False,
         'properties': {'answer': {'const': ''},
                        'citations': {'type': 'array', 'maxItems': 0},
                        'abstain': {'const': True}},
         'required': ['answer', 'citations', 'abstain']}]}


def alter_schema(payload, ids, arm):
    if arm not in ARMS:
        raise ValueError('unknown arm')
    value = copy.deepcopy(payload)
    if arm == 'branched':
        value['response_format']['json_schema']['schema'] = branch_schema(ids)
    return value


def answer_request(query, context, arm):
    """Capture the existing generator's request offline rather than duplicate its prompt."""
    response, connection = Mock(), Mock()
    response.status = 200
    response.read.return_value = b'{"choices":[{"finish_reason":"stop","message":{"content":"{\\"answer\\":\\"\\",\\"citations\\":[],\\"abstain\\":true}"}}]}'
    connection.getresponse.return_value = response
    with patch('rag_foundation.generation.http.client.HTTPConnection', return_value=connection):
        LocalGenerator().generate(query, context)
    payload = json.loads(connection.request.call_args.args[2])
    return alter_schema(payload, [c['chunk_id'] for c in context], arm)


class ExperimentGenerator(LocalGenerator):
    def generate_arm(self, query, context, arm):
        original_factory = http.client.HTTPConnection
        owner = self
        ids = [c['chunk_id'] for c in context]
        self.last_payload = None

        class SchemaConnection:
            def __init__(self, *args, **kwargs):
                self.connection = original_factory(*args, **kwargs)

            def request(self, method, url, body, headers):
                payload = alter_schema(json.loads(body), ids, arm)
                owner.last_payload = payload
                self.connection.request(method, url, json.dumps(payload).encode('utf-8'), headers)

            def getresponse(self):
                return self.connection.getresponse()

            def close(self):
                self.connection.close()

        with patch('rag_foundation.generation.http.client.HTTPConnection', SchemaConnection):
            return super().generate(query, context)


def shape_accepts(value, ids, arm):
    """Small independent schema-shape preflight, NOT a native GBNF interpreter.

    Leave semantic support and Python-only whitespace/uniqueness checks separate.
    """
    if arm not in ARMS or not isinstance(value, dict) or set(value) != {'answer', 'citations', 'abstain'}:
        return False
    answer, citations, abstain = value['answer'], value['citations'], value['abstain']
    if not isinstance(answer, str) or not isinstance(citations, list) or type(abstain) is not bool:
        return False
    if len(citations) > 3 or any(type(c) is not str or c not in ids for c in citations):
        return False
    if arm == 'legacy':
        return True
    return (answer == '' and citations == [] if abstain else 1 <= len(answer) <= 4000 and 1 <= len(citations) <= 3)
