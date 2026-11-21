"""Verify the six-call record without inference, downloads or a network connection."""
import argparse
from unittest.mock import Mock, patch

from live import HERE, REPO, SETUP, execute, sha
from rag_foundation.corpus import canonical_json
from rag_foundation.generation import strict_json


def read(path):
    return strict_json(path.read_text(encoding='utf-8'))


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def inspect():
    path = HERE / 'recorded-live.json'
    require(sha(path) == (HERE / 'recorded-live.sha256').read_text().strip(), 'raw archive changed')
    record = read(path)
    frozen = read(HERE / 'live.lock.json')['sha256']
    require(frozen == record['frozen_input_sha256'], 'archived freeze differs')
    require(all(sha(REPO / name) == expected for name, expected in frozen.items()), 'frozen inputs changed')
    pins = read(SETUP)
    require(record['model_sha256'] == pins['model']['expected_sha256'], 'model pin differs')
    require(record['server_sha256'] == pins['runtime']['server_sha256'], 'server pin differs')
    require(record['method'] == 'live-pinned-local-cpu' and record['server_returncode'] == 0, 'incomplete run')
    known = {'4.21.2': ('extended', 'e4default'), '5.1.0': ('simple', 'e5default')}
    raw, explained = [], []
    for row in record['rows']:
        gold, source = known[row['question_release']]
        matched = row['question_release'] == row['scope_release']
        for arm, step in row['arms'].items():
            outer = step['outcome']
            inner = outer if arm == 'unbound' else outer['pipeline']
            called = outer['generator_called']
            answer, ids, exact_truth, supplied_support = None, [], False, False
            if called:
                generation = inner['generation']
                require(generation['status'] == 'answered', 'expected six recorded accepted answers')
                answer, ids = generation['answer'], generation['citation_ids']
                raw.append(generation['raw_response'])
                require(answer in ('simple', 'extended'), 'non-literal answer needs explicit annotation')
                exact_truth = answer == gold
                supplied_support = exact_truth and (source in ids and all(i == source for i in ids))
            else:
                require(arm == 'bound' and not matched and outer['status'] == 'not_run'
                        and outer['reason'] == 'question_scope_release_mismatch' and step['request'] is None,
                        'wrong no-run interpretation')
            explained.append({'question_release': row['question_release'], 'scope_release': row['scope_release'],
                              'matched_release': matched, 'arm': arm, 'status': outer['status'],
                              'reason': outer['reason'], 'model_called': called, 'answer': answer, 'citation_ids': ids,
                              'exact_truth_for_question': exact_truth if called else None,
                              'cited_support_for_question': supplied_support if called else None})
    connections = []
    for envelope in raw:
        response = Mock()
        response.status = 200
        response.read.return_value = envelope.encode('utf-8')
        conn = Mock()
        conn.getresponse.return_value = response
        connections.append(conn)
    with patch('http.client.HTTPConnection', side_effect=connections) as http:
        require(execute(10240) == record['rows'], 'actual retrieval/request/raw-contract replay differs')
        require(http.call_count == len(raw) == 6, 'wrong number of actual model calls')

    arms = {}
    for arm in ('unbound', 'bound'):
        data = [r for r in explained if r['arm'] == arm]
        arms[arm] = {
            'model_calls': sum(r['model_called'] for r in data),
            'diagonal_exact_supported': sum(r['matched_release'] and r['cited_support_for_question'] is True for r in data),
            'crossed_false_and_unsupported': sum(not r['matched_release'] and r['exact_truth_for_question'] is False
                                                 and r['cited_support_for_question'] is False for r in data),
            'crossed_no_run': sum(not r['matched_release'] and r['status'] == 'not_run' for r in data),
        }
    return {'method': 'finite exact-value and required-source rubric; not general semantic judging',
            'pairs': len(record['rows']), 'source_fact_families': 1, 'arms': arms, 'rows': explained}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    rendered = canonical_json(inspect())
    if args.check:
        require((HERE / 'live-summary.json').read_bytes() == rendered.encode('utf-8'), 'live summary changed')
        print('Six-call recorded CPU comparison matches offline request/contract replay.')
    else:
        print(rendered, end='')
