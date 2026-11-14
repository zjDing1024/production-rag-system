"""Offline evidence-integrity and format audit. Human review supplies semantics.

Does not run a model, contact a server, normalize failed answers, or infer entailment.
"""
from collections import Counter
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def strict_json(text):
    def pairs(items):
        obj = {}
        for key, value in items:
            if key in obj:
                raise ValueError('duplicate JSON key')
            obj[key] = value
        return obj
    def reject(value):
        raise ValueError('non-finite JSON constant')
    return json.loads(text, object_pairs_hook=pairs, parse_constant=reject)


def inspect_form(content, mode, allowed_ids, finish='stop'):
    if mode == 'baseline_text':
        return {'json_shape_valid': None,
                'contract_valid': finish == 'stop' and (content == 'INSUFFICIENT_EVIDENCE' or '[S1]' in content),
                'abstain_signal': content == 'INSUFFICIENT_EVIDENCE'}
    try:
        value = strict_json(content)
    except (ValueError, TypeError):
        return {'json_shape_valid': False, 'contract_valid': False, 'abstain_signal': None}
    shape = (isinstance(value, dict) and set(value) == {'answer', 'citations', 'abstain'}
             and isinstance(value['answer'], str) and type(value['abstain']) is bool
             and isinstance(value['citations'], list)
             and all(isinstance(x, str) for x in value['citations']))
    if not shape:
        return {'json_shape_valid': False, 'contract_valid': False, 'abstain_signal': None}
    cites = value['citations']
    membership = len(cites) <= 3 and len(set(cites)) == len(cites) and all(x in allowed_ids for x in cites)
    cross_field = (value['answer'] == '' and not cites) if value['abstain'] else (bool(value['answer'].strip()) and bool(cites))
    return {'json_shape_valid': True, 'contract_valid': bool(finish == 'stop' and membership and cross_field and len(value['answer']) <= 4000),
            'abstain_signal': value['abstain']}


def audit(root=HERE):
    fixture = json.loads((root / 'cases.json').read_text())
    lock = json.loads((root / 'cases.lock.json').read_text())
    if sha(root / 'cases.json') != lock['cases_sha256']:
        raise ValueError('frozen cases changed')
    for name, digest in json.loads((root / 'recorded-files.sha256.json').read_text()).items():
        if Path(name).name != name or sha(root / 'recorded' / name) != digest:
            raise ValueError('recorded file changed: ' + name)
    manifest = json.loads((root / 'recorded/manifest.json').read_text())
    if manifest['cases_sha256'] != lock['cases_sha256'] or manifest['runner_sha256'] != sha(root / 'run_experiment.py'):
        raise ValueError('runner or fixture differs from actual run')
    cases = {x['id']: x for x in fixture['cases']}
    expected_order = [(c['id'], m) for c in fixture['cases'] for m in fixture['plan']['fixed_context_modes']]
    expected_order += [(c['id'], 'retrieval_pipeline') for c in fixture['cases']]
    actual_order = [(r['case_id'], r['mode']) for r in manifest['requests']]
    if actual_order != expected_order:
        raise ValueError('missing or reordered attempts')
    reviews = json.loads((root / 'manual-review.json').read_text())['reviews']
    if [(r['case_id'], r['mode']) for r in reviews] != actual_order:
        raise ValueError('manual review coverage differs from attempts')
    rows = []
    for entry, review in zip(manifest['requests'], reviews):
        case = cases[entry['case_id']]
        invoked, runtime_failure, gate = True, False, False
        if entry['mode'] == 'retrieval_pipeline':
            result = json.loads((root / 'recorded' / entry['result_file']).read_text())
            invoked = entry['model_invoked']
            gate = result['reason'] == 'no_retrieved_context'
            runtime_failure = result['status'] == 'transport_error'
            allowed_ids = [x['chunk_id'] for x in result['context']]
            raw = result['raw_response']
        else:
            raw = (root / 'recorded' / entry['raw_file']).read_text()
            allowed_ids = ['S1']
            runtime_failure = entry['runtime_status'] != 'completed'
        form = {'json_shape_valid': None, 'contract_valid': None, 'abstain_signal': None}
        finish = None
        if invoked and not runtime_failure:
            envelope = strict_json(raw)
            content = envelope['choices'][0]['message']['content']
            finish = envelope['choices'][0]['finish_reason']
            form = inspect_form(content, entry['mode'], allowed_ids, finish)
        decision_correct = review['verdict'] in {'correct_supported_answer', 'correct_abstention', 'correct_gate_abstention'}
        strict_pass = decision_correct and (gate or form['contract_valid'] is True)
        rows.append({'case_id': entry['case_id'], 'language': case['language'], 'category': case['category'],
                     'mode': entry['mode'], 'model_invoked': invoked, 'runtime_failure': runtime_failure,
                     'gate_abstention': gate, 'finish_reason': finish, **form,
                     'manual_verdict': review['verdict'], 'semantic_decision_correct': decision_correct,
                     'unsupported_claim_in_raw': review['unsupported_claim_in_raw'],
                     'strict_pass': strict_pass})
    aggregate = {}
    for mode in ('baseline_text', 'structured_json_schema', 'retrieval_pipeline'):
        subset = [r for r in rows if r['mode'] == mode]
        negative = [r for r in subset if r['category'] != 'answerable']
        aggregate[mode] = {
            'cases': len(subset), 'model_invocations': sum(r['model_invoked'] for r in subset),
            'runtime_failures': sum(r['runtime_failure'] for r in subset),
            'json_shape_valid': sum(r['json_shape_valid'] is True for r in subset),
            'contract_valid_model_outputs': sum(r['contract_valid'] is True for r in subset),
            'supported_correct_answerable': sum(r['manual_verdict'] == 'correct_supported_answer' for r in subset),
            'answerable_denominator': sum(r['category'] == 'answerable' for r in subset),
            'valid_model_abstentions_on_negatives': sum(r['manual_verdict'] == 'correct_abstention' and r['contract_valid'] is True for r in negative),
            'gate_abstentions_on_negatives': sum(r['gate_abstention'] for r in negative),
            'negative_denominator': len(negative),
            'semantic_decisions_correct': sum(r['semantic_decision_correct'] for r in subset),
            'unsupported_claims_in_raw': sum(r['unsupported_claim_in_raw'] for r in subset),
            'unsupported_claims_accepted_by_contract': sum(r['unsupported_claim_in_raw'] and r['contract_valid'] is True for r in subset),
            'strict_passes': sum(r['strict_pass'] for r in subset),
            'verdict_counts': dict(sorted(Counter(r['manual_verdict'] for r in subset).items()))}
    return {'record_integrity': 'verified', 'semantic_judge': 'manual review, not an automatic entailment test',
            'causal_limit': 'output instructions and response_format both change; no grammar-only causal claim',
            'aggregate': aggregate, 'rows': rows}


if __name__ == '__main__':
    print(json.dumps(audit(), ensure_ascii=False, indent=2))
