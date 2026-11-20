"""Reuse the same previously frozen branched generator, not a new production default."""
import importlib.util
from pathlib import Path
import sys
HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
sys.path.insert(0,str(REPO/'src'))
spec=importlib.util.spec_from_file_location('prior_typed_adapter',REPO/'experiments/typed-scope-v1/adapter.py')
previous=importlib.util.module_from_spec(spec);spec.loader.exec_module(previous)
BranchedGenerator=previous.BranchedGenerator
expected_request=previous.expected_request
from rag_foundation.corpus import Chunk
from rag_foundation.scope_gate import Scope
from rag_foundation.scoped_pipeline import ClaimIndex,ScopedGenerationPipeline


def make_pipeline(case,generator=None):
    # Gold/rubric/source-reference metadata is never passed to the actual pipeline.
    index=ClaimIndex([Chunk(**row) for row in case['chunks']],case['catalog'])
    return ScopedGenerationPipeline(index,generator)


def run_case(case,arm,generator=None):
    pipeline=make_pipeline(case,generator)
    return pipeline.answer(case['request']['query'],Scope.from_dict(case['request']['scope']),
                           scope_gate=arm=='scoped',**case['options'])
