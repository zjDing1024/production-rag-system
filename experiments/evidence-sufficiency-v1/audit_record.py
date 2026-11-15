"""Offline replay of recorded decisions and manual semantic judgments; no inference."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def quote_diagnosis(fixture, results, attempts):
    cases = {c['id']: c for c in fixture['cases'] + fixture['diagnostics']}
    rows, raw_true = [], 0
    def normal(text):
        return re.sub(r'\s+', ' ', text).strip()
    for key, attempt in attempts.items():
        if not attempt['gate_invoked']:
            continue
        result = results[key]
        gate = result.get('evidence_gate', result)
        outer = json.loads(gate['raw_response'])
        decision = json.loads(outer['choices'][0]['message']['content'])
        raw_true += decision['sufficient'] is True
        sources = {c['chunk_id']: c['text'] for c in cases[key[0]]['context']}
        seen = set()
        for index, evidence in enumerate(decision['evidence']):
            quote, cid = evidence['quote'], evidence['chunk_id']
            chosen = sources.get(cid, '')
            if quote in chosen:
                category = 'exact_selected_span'
            elif normal(quote) in normal(chosen):
                category = 'whitespace_only_selected_span'
            elif any(normal(quote) in normal(text) for source_id, text in sources.items() if source_id != cid):
                category = 'other_supplied_chunk'
            else:
                category = 'not_found_after_whitespace_normalization'
            pair = (cid, quote)
            rows.append({'case_id': key[0], 'quote_index': index, 'category': category,
                         'duplicate_pair': pair in seen})
            seen.add(pair)
    return rows, raw_true


def audit(root=HERE):
    fixture = json.loads((root / 'cases.json').read_text())
    lock = json.loads((root / 'cases.lock.json').read_text())
    if sha(root / 'cases.json') != lock['cases_sha256']:
        raise ValueError('frozen cases changed')
    index = json.loads((root / 'recorded-files.sha256.json').read_text())
    for name, expected in index.items():
        if Path(name).name != name or sha(root / 'recorded' / name) != expected:
            raise ValueError('recorded file changed: ' + name)
    manifest = json.loads((root / 'recorded/manifest.json').read_text())
    if manifest['cases_sha256'] != lock['cases_sha256'] or manifest['runner_sha256'] != sha(root / 'run_experiment.py'):
        raise ValueError('runner or inputs do not match actual execution')
    expected = [(case['id'], condition) for case in fixture['cases'] for condition in ('off', 'on')]
    expected += [(case['id'], 'diagnostic') for case in fixture['diagnostics']]
    if [(row['case_id'], row['condition']) for row in manifest['attempts']] != expected:
        raise ValueError('attempts are missing, duplicated, or reordered')
    manual = json.loads((root / 'manual-review.json').read_text())
    reviewed = {(r['case_id'], r['condition']): r for r in manual['reviews']}
    if set(reviewed) != set(expected) or len(reviewed) != len(manual['reviews']):
        raise ValueError('manual review coverage differs from attempts')
    result_map = {}
    attempts = {}
    for attempt in manifest['attempts']:
        key = (attempt['case_id'], attempt['condition'])
        path = root / 'recorded' / attempt['file']
        if sha(path) != attempt['sha256']:
            raise ValueError('manifest file hash differs')
        result_map[key] = json.loads(path.read_text())
        attempts[key] = attempt
    rows = []
    for case in fixture['cases']:
        off = result_map[(case['id'], 'off')]
        on = result_map[(case['id'], 'on')]
        if off['context'] != case['context'] or on['context'] != case['context'] or off['retrieval'] != on['retrieval']:
            raise ValueError('paired retrieval or actual supplied context changed')
        gate = on.get('evidence_gate')
        expected_sufficient = case['manual_sufficiency']
        gate_status = gate['status'] if gate else 'not_invoked_no_context'
        if gate_status in ('sufficient', 'insufficient'):
            # Revalidate accepted quote provenance, NOT whether a quote entails a claim.
            if gate_status == 'insufficient' and gate['evidence']:
                raise ValueError('invalid abstention evidence')
            if gate_status == 'sufficient':
                sources = {h['chunk_id']: h['text'] for h in case['context']}
                if not gate['evidence']:
                    raise ValueError('missing evidence for sufficient decision')
                for evidence in gate['evidence']:
                    if evidence['quote'] not in sources.get(evidence['chunk_id'], ''):
                        raise ValueError('accepted quote lacks exact provenance')
        if gate_status in ('insufficient', 'invalid_response', 'transport_error') and attempts[(case['id'], 'on')]['generator_invoked']:
            raise ValueError('generator was invoked after non-passing gate')
        reviews = {condition: reviewed[(case['id'], condition)] for condition in ('off', 'on')}
        rows.append({'case_id': case['id'], 'category': case['category'], 'answer_kind': case['answer_kind'],
                     'language': case['language'], 'manual_sufficient': expected_sufficient,
                     'has_context': bool(case['context']), 'gate_status': gate_status,
                     'off_status': off['status'], 'on_status': on['status'],
                     'off_verdict': reviews['off']['verdict'], 'on_verdict': reviews['on']['verdict'],
                     'additional_correct_evidence_stop': bool(case['context']) and not expected_sufficient and gate_status == 'insufficient',
                     'additional_false_evidence_stop': bool(case['context']) and expected_sufficient and gate_status == 'insufficient',
                     'gate_protocol_failure': gate_status in ('invalid_response', 'transport_error'),
                     'off_supported_correct': reviews['off']['verdict'] == 'supported_correct_answer',
                     'on_supported_correct': reviews['on']['verdict'] == 'supported_correct_answer',
                     'prevented_accepted_unsupported_answer_by_valid_stop': reviews['off']['verdict'] == 'unsupported_answer' and gate_status == 'insufficient'})
    nonempty = [r for r in rows if r['has_context']]
    diagnostics = []
    for case in fixture['diagnostics']:
        result = result_map[(case['id'], 'diagnostic')]
        diagnostics.append({'case_id': case['id'], 'manual_sufficient': case['manual_sufficiency'],
                            'status': result['status'], 'verdict': reviewed[(case['id'], 'diagnostic')]['verdict'],
                            'correct_valid_decision': result['status'] == ('sufficient' if case['manual_sufficiency'] else 'insufficient')})
    quote_rows, raw_true = quote_diagnosis(fixture, result_map, attempts)
    quote_record = json.loads((root / 'quote-diagnostics.json').read_text())
    quote_counts = dict(Counter(q['category'] for q in quote_rows))
    if (quote_rows != quote_record['quote_rows'] or quote_counts != quote_record['quote_category_counts']
            or sum(row['duplicate_pair'] for row in quote_rows) != quote_record['duplicate_pairs']):
        raise ValueError('post-hoc quote diagnosis differs from raw evidence')
    summary = {
        'fresh_cases': len(rows), 'bilingual_fact_pairs': len(rows) // 2,
        'nonempty_context_cases': len(nonempty), 'existing_no_context_exits_excluded': len(rows) - len(nonempty),
        'sufficient_context_denominator': sum(r['manual_sufficient'] for r in nonempty),
        'insufficient_nonempty_denominator': sum(not r['manual_sufficient'] for r in nonempty),
        'gate_status_counts_nonempty': dict(sorted(Counter(r['gate_status'] for r in nonempty).items())),
        'additional_correct_evidence_stops': sum(r['additional_correct_evidence_stop'] for r in rows),
        'additional_false_evidence_stops': sum(r['additional_false_evidence_stop'] for r in rows),
        'gate_protocol_failures_on_sufficient': sum(r['gate_protocol_failure'] and r['manual_sufficient'] for r in rows),
        'gate_protocol_failures_on_insufficient': sum(r['gate_protocol_failure'] and not r['manual_sufficient'] for r in rows),
        'supported_correct_answer_coverage_off': sum(r['off_supported_correct'] for r in rows),
        'supported_correct_answer_coverage_on': sum(r['on_supported_correct'] for r in rows),
        'prevented_accepted_unsupported_by_valid_evidence_stop': sum(r['prevented_accepted_unsupported_answer_by_valid_stop'] for r in rows),
        'generator_calls_off': sum(a['generator_invoked'] for a in manifest['attempts'] if a['condition'] == 'off'),
        'generator_calls_on': sum(a['generator_invoked'] for a in manifest['attempts'] if a['condition'] == 'on'),
        'gate_calls_pipeline': sum(a['gate_invoked'] for a in manifest['attempts'] if a['condition'] == 'on'),
        'gate_calls_diagnostic': len(diagnostics),
        'raw_gate_sufficient_true': raw_true,
        'posthoc_quote_categories': quote_counts,
        'diagnostic_correct_valid_decisions': sum(d['correct_valid_decision'] for d in diagnostics),
        'diagnostic_denominator': len(diagnostics)}
    return {'record_integrity': 'verified', 'semantic_labels': 'frozen manual assessment of actual context by AI assistants; outcomes reviewed by AI assistants',
            'summary': summary, 'pairs': rows, 'diagnostics': diagnostics}


if __name__ == '__main__':
    print(json.dumps(audit(), ensure_ascii=False, indent=2))
