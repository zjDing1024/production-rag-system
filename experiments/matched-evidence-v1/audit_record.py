"""Offline record/contract replay. AI semantic labels are disclosed, not proved by this audit."""
from collections import Counter
import argparse
import hashlib
import json
from pathlib import Path
from unittest.mock import Mock, patch
from protocol import (ARMS, SpanSelector, ExperimentGenerator, answer_request,
                      make_selector_payload, strict_json, shape_accepts)
from build_fixture import build
from preflight_contracts import preflight

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def read(path):
    return strict_json(path.read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def fake_connection(raw, status=200):
    require(isinstance(raw, str), 'archive requires a captured HTTP response')
    conn, response = Mock(), Mock()
    response.status = status
    response.read.return_value = raw.encode('utf-8')
    conn.getresponse.return_value = response
    return conn


def parsed(raw):
    try:
        return strict_json(strict_json(raw)['choices'][0]['message']['content'])
    except (ValueError, TypeError, KeyError, IndexError):
        return None


def audit(directory=HERE):
    fixture, lock = read(directory / 'cases.json'), read(directory / 'cases.lock.json')
    require(lock['status'] == 'frozen_before_execution' and sha(directory / 'cases.json') == lock['cases_sha256'],
            'fixture not frozen or hash changed')
    require(fixture == build(), 'source-derived fixture rebuild mismatch')
    for name, expected in lock['file_sha256'].items():
        require(sha(REPO / name) == expected, 'frozen file changed: ' + name)
    require(read(directory / 'preflight.json') == preflight(), 'preflight replay mismatch')
    cases = {c['id']: c for c in fixture['cases']}
    require(len(cases) == 16, 'unexpected case set')
    pair_ids = sorted({c['pair_id'] for c in cases.values()})
    for pair in pair_ids:
        a, b = [c for c in cases.values() if c['pair_id'] == pair]
        require(a['query'] == b['query'] and a['offered_sufficient'] != b['offered_sufficient'], 'unmatched query/labels')
        for c in (a, b):
            require([len(s['text']) for s in c['spans']] == [227, 235], 'span count/length changed')
    record = directory / 'recorded'
    index = read(directory / 'recorded-files.sha256.json')
    require(set(index) == {p.name for p in record.glob('*.json')}, 'archive file list changed')
    for name, expected in index.items():
        require(Path(name).name == name and sha(record / name) == expected, 'record hash changed: ' + name)
    manifest = read(record / 'manifest.json')
    require(manifest['cases_sha256'] == lock['cases_sha256'] and manifest['file_sha256'] == lock['file_sha256'],
            'manifest frozen inputs mismatch')
    require(manifest['server_stopped'] and not manifest.get('execution_error'), 'execution not complete')
    require([e['case_id'] for e in manifest['attempts']] == list(cases), 'case order changed')
    sources = read(REPO / 'experiments/local-generation-smoke/sources.json')
    require(manifest['model_sha256'] == sources['model']['expected_sha256'] and
            manifest['runtime_sha256'] == sources['runtime']['server_sha256'], 'asset pin mismatch')
    annotation = read(directory / 'assistant-review.json')
    reviews = {(r['case_id'], r['arm']): r for r in annotation['rows']}
    require(len(reviews) == len(annotation['rows']) == 32 and
            set(reviews) == {(c, a) for c in cases for a in ARMS}, 'semantic annotation set mismatch')
    rows, selections = [], []
    for entry in manifest['attempts']:
        case = cases[entry['case_id']]
        require(entry['complete'], 'incomplete attempt')
        for kind in ('request', 'result'):
            require(sha(record / entry[kind + '_file']) == entry[kind + '_sha256'], 'manifest hash mismatch')
        request, result = read(record / entry['request_file']), read(record / entry['result_file'])
        require(request == make_selector_payload(case['query'], case['spans'], 'numbered_span'), 'selector request mismatch')
        require(result['case_id'] == case['id'], 'result identity mismatch')
        selection = result['selector']
        with patch('protocol.http.client.HTTPConnection', return_value=fake_connection(selection['raw_response'], selection['http_status'])):
            replay = SpanSelector().select(case['query'], case['spans'], 'numbered_span')
        require(replay == selection, 'selector replay mismatch')
        require(entry['selector_status'] == selection['status'], 'manifest selector mismatch')
        selected = selection['status'] == 'selected'
        support = selected and selection['selected_span_ids'] == case['supporting_span_ids']
        expected_arms = case['generator_arm_order'] if selected else []
        require(list(result['generations']) == entry['generator_arms'] == expected_arms, 'generator routing/order mismatch')
        selections.append({'case_id': case['id'], 'pair_id': case['pair_id'], 'scope': case['scope'],
            'condition': case['condition'], 'answer_kind': case['answer_kind'], 'language': case['language'],
            'offered_sufficient': case['offered_sufficient'], 'status': selection['status'],
            'selected_ids': selection['selected_span_ids'], 'selected_support': support,
            'legitimate_refusal': selection['status'] == 'insufficient' and not case['offered_sufficient'],
            'false_refusal': selection['status'] == 'insufficient' and case['offered_sufficient']})
        for arm in ARMS:
            generation = result['generations'].get(arm)
            output, raw = None, None
            if generation:
                require(generation['request'] == answer_request(case['query'], selection['selected_context'], arm),
                        'generator request mismatch')
                output = generation['result']
                status = int(output['reason'][5:]) if output['status'] == 'transport_error' and output['reason'].startswith('http_') else 200
                with patch('protocol.http.client.HTTPConnection', return_value=fake_connection(output['raw_response'], status)):
                    replay = ExperimentGenerator().generate_arm(case['query'], selection['selected_context'], arm)
                require(replay == output, 'generator replay mismatch')
                raw = parsed(output['raw_response'])
            review = reviews[(case['id'], arm)]
            correct = review['accepted_supported_correct']
            require(type(correct) is bool and isinstance(review['rationale'], str) and review['rationale'], 'bad semantic annotation')
            require(review['raw_answer_assessment'] in ('supported_correct', 'unsupported_or_wrong', 'refusal',
                    'not_generated', 'no_parseable_answer'), 'unknown raw semantic assessment')
            if correct:
                require(support and output and output['status'] == 'answered', 'impossible supported correct annotation')
            gen_status = output['status'] if output else None
            served_refusal = selection['status'] == 'insufficient' or gen_status == 'evidence_abstained'
            legit = served_refusal and not case['offered_sufficient']
            rows.append({'case_id': case['id'], 'pair_id': case['pair_id'], 'scope': case['scope'],
                'condition': case['condition'], 'answer_kind': case['answer_kind'], 'language': case['language'],
                'arm': arm, 'offered_sufficient': case['offered_sufficient'], 'selector_status': selection['status'],
                'selected_support': support, 'generator_called': bool(generation), 'generator_status': gen_status,
                'raw_schema_shape_valid': shape_accepts(raw, [c['chunk_id'] for c in selection['selected_context']], arm) if generation else None,
                'raw_answer': raw.get('answer') if isinstance(raw, dict) else None,
                'raw_answer_assessment': review['raw_answer_assessment'],
                'accepted_supported_correct': correct, 'legitimate_final_refusal': legit,
                'false_final_refusal': served_refusal and case['offered_sufficient'],
                'accepted_without_supporting_selected_evidence': gen_status == 'answered' and not support,
                'accepted_wrong_or_unsupported_answer': gen_status == 'answered' and not correct,
                'final_success': correct if case['offered_sufficient'] else legit})
    pairs = []
    for pair in pair_ids:
        selected = [r for r in selections if r['pair_id'] == pair]
        positive = next(r for r in selected if r['offered_sufficient'])
        negative = next(r for r in selected if not r['offered_sufficient'])
        pairs.append({'pair_id': pair, 'scope': positive['scope'], 'answer_kind': positive['answer_kind'],
            'selector_pair_success': positive['selected_support'] and negative['legitimate_refusal'],
            'final_pair_success': {a: all(r['final_success'] for r in rows if r['pair_id'] == pair and r['arm'] == a) for a in ARMS}})
    summary = {'rows': 16, 'matched_question_pairs': 8, 'fact_families': 4,
        'offered_sufficient': 8, 'offered_insufficient': 8,
        'selector_status_counts': dict(sorted(Counter(s['status'] for s in selections).items())),
        'supporting_selections': sum(s['selected_support'] for s in selections),
        'unsupported_selections': sum(s['status'] == 'selected' and not s['selected_support'] for s in selections),
        'legitimate_selector_refusals': sum(s['legitimate_refusal'] for s in selections),
        'false_selector_refusals': sum(s['false_refusal'] for s in selections),
        'correct_supported_selection_or_refusal_rows': sum(s['selected_support'] or s['legitimate_refusal'] for s in selections),
        'selector_pair_success': sum(p['selector_pair_success'] for p in pairs),
        'selector_by_scope': {scope: {
            'offered_sufficient': sum(s['offered_sufficient'] for s in selections if s['scope'] == scope),
            'offered_insufficient': sum(not s['offered_sufficient'] for s in selections if s['scope'] == scope),
            'supporting_selections': sum(s['selected_support'] for s in selections if s['scope'] == scope),
            'legitimate_refusals': sum(s['legitimate_refusal'] for s in selections if s['scope'] == scope),
            'complete_pairs': sum(p['selector_pair_success'] for p in pairs if p['scope'] == scope),
        } for scope in ('documentation', 'synthetic_runtime')},
        'generator_arms': {}}
    for arm in ARMS:
        arm_rows = [r for r in rows if r['arm'] == arm]
        summary['generator_arms'][arm] = {
            'calls': sum(r['generator_called'] for r in arm_rows),
            'status_counts': dict(sorted(Counter(r['generator_status'] for r in arm_rows if r['generator_called']).items())),
            'raw_schema_shape_valid': sum(r['raw_schema_shape_valid'] is True for r in arm_rows),
            'accepted_supported_correct': sum(r['accepted_supported_correct'] for r in arm_rows),
            'legitimate_final_refusals': sum(r['legitimate_final_refusal'] for r in arm_rows),
            'false_final_refusals': sum(r['false_final_refusal'] for r in arm_rows),
            'accepted_wrong_or_unsupported_answers': sum(r['accepted_wrong_or_unsupported_answer'] for r in arm_rows),
            'final_success_rows': sum(r['final_success'] for r in arm_rows),
            'final_pair_success': sum(p['final_pair_success'][arm] for p in pairs)}
    baselines = {}
    for name, policy in [('always_sufficient', lambda c: True), ('always_insufficient', lambda c: False),
                         ('documentation_only', lambda c: c['scope'] == 'documentation')]:
        baselines[name] = {'correct_rows': sum(policy(c) == c['offered_sufficient'] for c in cases.values()),
            'complete_pairs': sum(all(policy(c) == c['offered_sufficient'] for c in cases.values() if c['pair_id'] == p)
                                  for p in pair_ids)}
    return {'record_integrity': 'verified', 'semantic_labels': 'AI-authored, cross-checked by another AI assistant; not machine-proved or human annotation',
            'evidence_blind_baselines': baselines,
            'summary': summary, 'selection_rows': selections, 'paired_outcomes': pairs, 'outcome_rows': rows}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='compare Python objects with committed summary, avoiding shell encoding/line endings')
    args = parser.parse_args()
    value = audit()
    if args.check:
        require(value == read(HERE / 'summary.json'), 'saved summary differs from replay')
        print('Recorded summary matches offline replay.')
    else:
        print(json.dumps(value, ensure_ascii=False, indent=2))
