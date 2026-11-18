"""Same previously frozen branched generator for both experiment arms; no default change."""
import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
spec = importlib.util.spec_from_file_location('matched_contract', REPO / 'experiments/matched-evidence-v1/protocol.py')
previous = importlib.util.module_from_spec(spec)
spec.loader.exec_module(previous)
from rag_foundation.scope_gate import Scope, EvidenceRecord, answer, plan, parse_input, select_scope


class BranchedGenerator:
    def __init__(self, endpoint='http://127.0.0.1:8080', timeout=120):
        self.generator = previous.ExperimentGenerator(endpoint, timeout)
        self.last_payload = None

    def generate(self, query, context):
        result = self.generator.generate_arm(query, context, 'branched')
        self.last_payload = self.generator.last_payload
        return result


def expected_request(query, context):
    return previous.answer_request(query, context, 'branched')
