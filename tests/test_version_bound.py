"""Contract tests for the optional release guard, using no inference."""
from dataclasses import asdict
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock

from rag_foundation.corpus import Chunk, digest, write_chunks
from rag_foundation.scope_gate import Scope
from rag_foundation.scoped_pipeline import ClaimIndex, ScopedGenerationPipeline, chunks_fingerprint
from rag_foundation.version_bound import answer_with_version_binding, check_version

ROOT = Path(__file__).resolve().parents[1]
OLD = Scope('documentation', 'Express', 'query parser.default', '4.21.2')
NEW = Scope('documentation', 'Express', 'query parser.default', '5.1.0')
QUERY = '在 Express 5.1.0 中，query parser 的默认值是什么？'


def fixture():
    text = 'Express 5.1.0 initializes the query parser setting to simple.'
    sha = digest(text.encode('utf-8'))
    chunk = Chunk('release', 'doc', 'Original fixture', text, 'synthetic://release', sha,
                  'MIT', 0, len(text), 1, 1)
    catalog = {'schema_version': 1, 'complete': True, 'chunks_sha256': chunks_fingerprint([chunk]),
               'entries': [{'chunk_id': chunk.id, 'scope': asdict(NEW),
                            'claim': {'reviewed': True, 'chunk_text_sha256': sha,
                                      'start_char': 0, 'end_char': len(text), 'quote': text,
                                      'value_type': 'string', 'unit': 'fixture_literal', 'value': 'simple'}}]}
    return chunk, catalog


def pipe():
    chunk, catalog = fixture()
    return ScopedGenerationPipeline(ClaimIndex([chunk], catalog), Mock())


class VersionBindingTests(unittest.TestCase):
    def test_ascii_and_chinese_surrounding_text(self):
        for q, token in [('Express v5.1.0?', 'v5.1.0'), ('Express 5.1.0.', '5.1.0'),
                         ('版本5.1.0的配置？', '5.1.0'), (QUERY, '5.1.0')]:
            with self.subTest(q=q):
                answer = check_version(q, NEW)
                self.assertEqual(answer['status'], 'bound')
                obs, = answer['observations']
                self.assertEqual(q[obs['start']:obs['end']], token)

    def test_literal_mismatch(self):
        self.assertEqual(check_version(QUERY, OLD)['reason'], 'question_scope_release_mismatch')

    def test_unknown_or_ambiguous_mentions(self):
        for query, reason in [
            ('latest Express', 'no_explicit_release'),
            ('pkg5.1.0', 'no_explicit_release'),
            ('Express 4.21.2 / 5.1.0', 'ambiguous_release_mentions'),
            ('Use 5.1.0 and then 5.1.0', 'ambiguous_release_mentions'),
        ]:
            with self.subTest(query=query):
                self.assertEqual(check_version(query, NEW)['reason'], reason)

    def test_does_not_reduce_ranges_prereleases_or_wildcards_to_literal(self):
        for query in ('Express 5.1.0-rc.2', '5.1.0+build.01', '5.1', '5.1.0.0',
                      '5.1.0.x', '5.1.0.*', '5.1.0*', '>= 5.1.0', '≥5.1.0',
                      '5.1.0..1', 'v05.1.0', '^v5.1.0'):
            with self.subTest(query=query):
                self.assertEqual(check_version(query, NEW)['reason'], 'unsupported_release_token')

    def test_unsupported_scopes_remain_opt_in_only(self):
        for scope in (Scope('documentation', 'Express', 'query parser.default', 'latest'),
                      Scope('runtime', 'Express', 'query parser.default', observed_at='2025-04-03T00:00:00Z')):
            with self.subTest(scope=scope):
                self.assertEqual(check_version(QUERY, scope)['reason'], 'unsupported_documentation_scope')

    def test_guard_stops_before_scope_assessment_search_and_model(self):
        pipeline = pipe()
        pipeline.index.assess = Mock(side_effect=AssertionError('no scope assessment'))
        pipeline.index.bm25.search = Mock(side_effect=AssertionError('no BM25'))
        result = answer_with_version_binding(pipeline, QUERY, OLD, k=1)
        self.assertEqual((result['status'], result['reason']), ('not_run', 'question_scope_release_mismatch'))
        self.assertIsNone(result['pipeline'])
        self.assertFalse(result['generator_called'])
        pipeline.index.assess.assert_not_called()
        pipeline.index.bm25.search.assert_not_called()
        pipeline.generator.generate.assert_not_called()

    def test_matching_case_preserves_query_and_evidence(self):
        pipeline = pipe()
        pipeline.generator.generate.return_value = {'status': 'answered', 'reason': 'spy'}
        result = answer_with_version_binding(pipeline, QUERY, NEW, k=1)
        self.assertTrue(result['generator_called'])
        self.assertEqual(result['semantic_support'], 'unverified')
        pipeline.generator.generate.assert_called_once_with(QUERY, result['pipeline']['context'])
        self.assertEqual([r['chunk_id'] for r in result['pipeline']['context']], ['release'])

    def test_binding_does_not_infer_subject_or_fact(self):
        other = Scope('documentation', 'Another Project', 'another key.default', '5.1.0')
        pipeline = pipe()
        result = answer_with_version_binding(pipeline, QUERY, other, k=1)
        self.assertEqual(result['binding']['status'], 'bound')
        self.assertEqual(result['reason'], 'no_matching_scope')
        pipeline.generator.generate.assert_not_called()

    def test_wrong_subject_can_reach_if_catalog_supports_caller_scope(self):
        # Intent is not checked; this is a boundary counterexample, not a guarantee.
        result = answer_with_version_binding(ScopedGenerationPipeline(pipe().index),
                                             'Another Project 5.1.0 query parser?', NEW, k=1)
        self.assertEqual(result['status'], 'planned')
        self.assertEqual(result['binding']['status'], 'bound')

    def test_public_arguments_validated_before_any_branch(self):
        for options in ({'k': True}, {'k': 4}, {'context_characters': 0}, {'scan_limit': 0}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                answer_with_version_binding(pipe(), QUERY, OLD, **options)
        with self.assertRaises(ValueError):
            check_version('a'*2001, NEW)
        with self.assertRaises(ValueError):
            check_version(QUERY, asdict(NEW))

    def test_cli_offline_and_old_entrypoint_unchanged(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            chunk, catalog = fixture()
            write_chunks([chunk], root / 'chunks.jsonl')
            (root / 'catalog.json').write_text(json.dumps(catalog), encoding='utf-8')
            (root / 'request.json').write_text(json.dumps({'query': QUERY, 'scope': asdict(NEW)}), encoding='utf-8')
            options = ['--chunks', str(root / 'chunks.jsonl'), '--catalog', str(root / 'catalog.json'),
                       '--request', str(root / 'request.json'), '-k', '1']
            unbound = json.loads(subprocess.check_output(
                [sys.executable, '-m', 'rag_foundation.scoped_pipeline', '--scope-gate', *options], cwd=ROOT))
            bound = json.loads(subprocess.check_output(
                [sys.executable, '-m', 'rag_foundation.version_bound', *options], cwd=ROOT))
            self.assertEqual(bound['pipeline'], unbound)
            self.assertFalse(bound['generator_called'])

    def test_recorded_replay_exact_and_counts(self):
        run = subprocess.run([sys.executable, str(ROOT / 'experiments/version-binding-v1/replay.py'), '--check'],
                             cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        rows = json.loads((ROOT / 'experiments/version-binding-v1/report.json').read_text())
        self.assertEqual(rows['metrics'], {'crossed_release_rows': 4, 'crossed_stopped_by_binding': 4,
            'crossed_wrong_release_packed_unbound': 4, 'matched_release_rows': 4,
            'matched_supported_bound': 4, 'matched_supported_unbound': 4, 'model_calls': 0})
        controls = {(row['control'], row['assignment']): row for row in rows['catalog_control_rows']}
        for row in controls.values():
            self.assertEqual(row['unbound'], row['bound'])
        self.assertEqual(controls['positive','extra_assigned']['bound']['packed_ids'], ['e5default'])
        self.assertEqual(controls['positive','extra_unassigned']['bound']['reason'], 'catalog_incomplete')
        self.assertEqual(controls['older_only','complete']['bound']['reason'], 'no_matching_scope')
        self.assertEqual(controls['older_only','extra_unassigned']['bound']['reason'], 'catalog_incomplete')
        self.assertEqual(controls['explicit_only','complete']['bound']['reason'], 'no_matching_scope')
