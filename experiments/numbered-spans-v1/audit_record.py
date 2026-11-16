"""Offline integrity/contract replay; semantic review is an AI annotation, not an oracle."""
from collections import Counter
import hashlib
import json
from pathlib import Path
from unittest.mock import Mock, patch

from mechanics import ARMS, SpanSelector, LocalGenerator, make_payload, strict_json, validate_spans

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return strict_json(path.read_text(encoding='utf-8'))


def require(value, message):
    if not value:
        raise ValueError(message)


def connection_for(raw, status=200):
    require(isinstance(raw, str), 'this archive expects recorded HTTP responses')
    response, connection = Mock(), Mock()
    response.status = status
    response.read.return_value = raw.encode('utf-8')
    connection.getresponse.return_value = response
    return connection


def content(raw):
    try:
        return strict_json(strict_json(raw)['choices'][0]['message']['content'])
    except (ValueError, TypeError, KeyError, IndexError):
        return None


def audit(directory=HERE):
    fixture, lock = read(directory / 'cases.json'), read(directory / 'cases.lock.json')
    require(lock['status'] == 'frozen_before_execution', 'not frozen')
    require(digest(directory / 'cases.json') == lock['cases_sha256'], 'fixture hash changed')
    for name, expected in lock['implementation_sha256'].items():
        require(digest(REPO / name) == expected, 'frozen implementation changed: ' + name)
    spans = fixture['offered_spans']
    validate_spans(spans)
    for s in spans:
        path = REPO / s['source_path']
        text = path.read_text()
        require(digest(path) == s['source_sha256'], 'source hash changed')
        require(text[s['char_start']:s['char_end']] == s['text'], 'source span changed')
        require(''.join(text.splitlines(keepends=True)[s['line_start'] - 1:s['line_end']]) == s['text'],
                'line provenance changed')
    cases = fixture['cases']
    require(len(cases) == 16 and len({c['id'] for c in cases}) == 16, 'unexpected case set')
    require(Counter((c['answer_kind'], c['language'], c['category']) for c in cases)
            == Counter({(k, l, cat): 2 for k in ('numeric', 'nonnumeric') for l in ('en', 'zh')
                        for cat in ('answerable', 'related_unanswerable')}), 'fixture balance changed')
    for c in cases:
        require(c['offered_sufficient'] == (c['category'] == 'answerable'), 'label/category mismatch')
        require(len(c['supporting_span_ids']) == int(c['offered_sufficient']), 'single-span gold required')
        require(set(c['supporting_span_ids']) <= {s['span_id'] for s in spans}, 'invalid gold')
    index = read(directory / 'recorded-files.sha256.json')
    recorded = directory / 'recorded'
    require(set(index) == {p.name for p in recorded.glob('*.json')}, 'archive file list changed')
    for name, expected in index.items():
        require(Path(name).name == name and digest(recorded / name) == expected, 'record hash changed: ' + name)
    manifest = read(recorded / 'manifest.json')
    require(manifest['cases_sha256'] == lock['cases_sha256'], 'run fixture mismatch')
    require(manifest['implementation_sha256'] == lock['implementation_sha256'], 'run code mismatch')
    source = read(REPO / 'experiments/local-generation-smoke/sources.json')
    require(manifest['model_sha256'] == source['model']['expected_sha256'], 'model mismatch')
    require(manifest['runtime_sha256'] == source['runtime']['server_sha256'], 'runtime mismatch')
    require(manifest['server_stopped'] and not manifest.get('execution_error'), 'incomplete execution')
    expected_order = [(c['id'], a) for c in cases for a in c['arm_order']]
    require([(e['case_id'], e['arm']) for e in manifest['attempts']] == expected_order, 'run order changed')
    review = read(directory / 'assistant-review.json')
    reviews = {(r['case_id'], r['arm']): r for r in review['rows']}
    require(len(reviews) == len(review['rows']) == 32 and set(reviews) == set(expected_order), 'review set changed')
    rows, quote_diagnostics = [], []
    by_id = {c['id']: c for c in cases}
    for entry in manifest['attempts']:
        case, arm = by_id[entry['case_id']], entry['arm']
        for key in ('request', 'result'):
            require(digest(recorded / entry[key + '_file']) == entry[key + '_sha256'], 'manifest file mismatch')
        request = read(recorded / entry['request_file'])
        require(request == make_payload(case['query'], spans, arm), 'recorded prompt differs from frozen mechanics')
        result = read(recorded / entry['result_file'])
        require((result['case_id'], result['arm']) == (case['id'], arm), 'result identity changed')
        selector = result['selector']
        with patch('mechanics.http.client.HTTPConnection', return_value=connection_for(
                selector['raw_response'], selector['http_status'])):
            replayed = SpanSelector().select(case['query'], spans, arm)
        require(replayed == selector, 'selector contract replay mismatch')
        require(result['generator_invoked'] == (selector['status'] == 'selected'), 'generator routing mismatch')
        require(entry['generator_invoked'] == result['generator_invoked'], 'manifest routing mismatch')
        require(entry['selector_status'] == selector['status'], 'manifest selector status mismatch')
        require(entry['selected_span_ids'] == selector['selected_span_ids'], 'manifest selection mismatch')
        generation = result['generator']
        if result['generator_invoked']:
            with patch('rag_foundation.generation.http.client.HTTPConnection',
                       return_value=connection_for(generation['raw_response'])):
                replayed = LocalGenerator().generate(case['query'], selector['selected_context'])
            require(replayed == generation, 'generator contract replay mismatch')
        else:
            require(generation is None, 'unexpected generator output')
        gen_status = generation['status'] if generation else None
        require(entry['generator_status'] == gen_status, 'manifest generator status mismatch')
        selected_support = bool(selector['selected_span_ids']) and all(
            sid in case['supporting_span_ids'] for sid in selector['selected_span_ids'])
        annotation = reviews[(case['id'], arm)]
        correct = annotation['accepted_answer_supported_correct']
        require(type(correct) is bool and isinstance(annotation['rationale'], str) and annotation['rationale'],
                'invalid semantic annotation')
        if correct:
            require(selected_support and gen_status == 'answered', 'impossible accepted correct annotation')
        raw_selection = content(selector['raw_response'])
        raw_gen = content(generation['raw_response']) if generation else None
        if arm == 'exact_quote' and isinstance(raw_selection, dict):
            for selection in raw_selection.get('selections', []):
                quote = selection.get('quote')
                original = spans[selection['span_id'] - 1]['text']
                quote_diagnostics.append({'case_id': case['id'], 'span_id': selection['span_id'],
                    'category': 'only_missing_final_newline' if quote + '\n' == original
                        else 'other_modified_or_partial_text',
                    'finish_reason': strict_json(selector['raw_response'])['choices'][0]['finish_reason']})
        require(annotation['raw_answer_assessment'] in (
            'not_generated', 'supported_correct', 'unsupported_or_wrong', 'refusal', 'no_parseable_answer'),
            'unknown raw answer review')
        rows.append({'case_id': case['id'], 'arm': arm, 'category': case['category'],
                     'answer_kind': case['answer_kind'], 'language': case['language'],
                     'offered_sufficient': case['offered_sufficient'],
                     'selector_status': selector['status'],
                     'raw_sufficient': raw_selection.get('sufficient') if isinstance(raw_selection, dict) else None,
                     'raw_selected_ids': [s.get('span_id') for s in raw_selection.get('selections', [])]
                         if isinstance(raw_selection, dict) else [],
                     'resolved_span_ids': selector['selected_span_ids'],
                     'selected_semantic_support': selected_support,
                     'legitimate_selector_refusal': selector['status'] == 'insufficient' and not case['offered_sufficient'],
                     'false_selector_refusal': selector['status'] == 'insufficient' and case['offered_sufficient'],
                     'generator_invoked': result['generator_invoked'], 'generator_status': gen_status,
                     'legitimate_generator_refusal': gen_status == 'evidence_abstained' and not case['offered_sufficient'],
                     'accepted_answer_supported_correct': correct,
                     'raw_answer_assessment': annotation['raw_answer_assessment'],
                     'raw_answer': raw_gen.get('answer') if isinstance(raw_gen, dict) else None})
    require(sorted(quote_diagnostics, key=lambda r: r['case_id']) ==
            read(directory / 'quote-diagnostics.json')['rows'], 'posthoc diagnostic mismatch')
    summaries = {}
    for arm in ARMS:
        arm_rows = [r for r in rows if r['arm'] == arm]
        summaries[arm] = {
            'cases': len(arm_rows), 'offered_sufficient': sum(r['offered_sufficient'] for r in arm_rows),
            'offered_insufficient': sum(not r['offered_sufficient'] for r in arm_rows),
            'selector_status_counts': dict(sorted(Counter(r['selector_status'] for r in arm_rows).items())),
            'contract_valid_selections': sum(r['selector_status'] == 'selected' for r in arm_rows),
            'selected_semantically_supporting': sum(r['selected_semantic_support'] for r in arm_rows),
            'legitimate_selector_refusals': sum(r['legitimate_selector_refusal'] for r in arm_rows),
            'false_selector_refusals': sum(r['false_selector_refusal'] for r in arm_rows),
            'generator_calls': sum(r['generator_invoked'] for r in arm_rows),
            'generator_status_counts': dict(sorted(Counter(r['generator_status'] for r in arm_rows if r['generator_invoked']).items())),
            'accepted_supported_correct_answers': sum(r['accepted_answer_supported_correct'] for r in arm_rows),
            'raw_supported_correct_answers': sum(r['raw_answer_assessment'] == 'supported_correct' for r in arm_rows),
            'legitimate_generator_refusals': sum(r['legitimate_generator_refusal'] for r in arm_rows),
            'by_answer_kind': {kind: {
                'answerable_denominator': sum(r['offered_sufficient'] for r in arm_rows if r['answer_kind'] == kind),
                'related_unanswerable_denominator': sum(not r['offered_sufficient'] for r in arm_rows if r['answer_kind'] == kind),
                'supported_selections': sum(r['selected_semantic_support'] for r in arm_rows if r['answer_kind'] == kind),
                'legitimate_selector_refusals': sum(r['legitimate_selector_refusal'] for r in arm_rows if r['answer_kind'] == kind),
                'false_selector_refusals': sum(r['false_selector_refusal'] for r in arm_rows if r['answer_kind'] == kind),
            } for kind in ('numeric', 'nonnumeric')},
        }
    return {'record_integrity': 'verified', 'semantic_review': 'AI-authored and second-AI-reviewed; not automatically proved',
            'scope': '4 fact families; 16 bilingual category questions; curated offered evidence, not retrieval ranking or held-out benchmark',
            'summary': summaries,
            'posthoc_quote_categories': dict(sorted(Counter(r['category'] for r in quote_diagnostics).items())),
            'rows': rows}


if __name__ == '__main__':
    print(json.dumps(audit(), ensure_ascii=False, indent=2))
