"""Author-time deterministic fixture construction, not a retriever or telemetry reader."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
BASE = '7a74ca741ae1e813ec52e95329ba697c7aaa0aa7'
SOURCE = 'data/corpus/flask/config.rst'
REV = 'ab8149664182b662453a563161aa89013c806dc9'
STAMP = '2030-04-05T10:00:00Z'


def render(fields):
    widths = {'subject': 12, 'setting': 24, 'value': 16}
    return '\n'.join(f'{k}: {str(v):<{widths.get(k, 0)}}' for k, v in fields.items()) + '\n'


def doc_note(key, literal, normalized):
    path = REPO / SOURCE
    text = path.read_text(encoding='utf-8')
    start = text.index('.. py:data:: ' + key + '\n')
    stop = text.find('.. py:data:: ', start + 1)
    block = text[start:stop if stop != -1 else len(text)]
    anchors = []
    for target in ('.. py:data:: ' + key, 'Default: ' + literal):
        offset = start + block.index(target)
        anchors.append({'text': target, 'char_start': offset, 'char_end': offset + len(target),
                        'line_start': text[:offset].count('\n') + 1})
    fields = {'source_kind': 'documentation_note', 'subject': 'Flask 3.1.0',
              'observed_at': 'not_applicable', 'setting': key, 'value': normalized,
              'value_kind': 'documented_default', 'notice': 'Source-derived note; not a runtime observation.'}
    return {'text': render(fields), 'fields': fields, 'provenance': {
        'type': 'original_structured_note_from_official_source', 'source_path': SOURCE,
        'source_sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'anchors': anchors,
        'transformation': 'Join setting header and Default from the same configuration section; normalize RST quotes and numeric underscores. Not a contiguous verbatim excerpt.',
        'license': 'BSD-3-Clause'}, 'source_url': f'https://github.com/pallets/flask/blob/{REV}/docs/config.rst#L{anchors[0]["line_start"]}'}


def snapshot(subject, setting, value):
    fields = {'source_kind': 'synthetic_snapshot', 'subject': subject, 'observed_at': STAMP,
              'setting': setting, 'value': value, 'value_kind': 'effective_snapshot',
              'notice': 'Invented fixture; not real application telemetry.'}
    return {'text': render(fields), 'fields': fields,
            'provenance': {'type': 'original_synthetic_fixture', 'license': 'MIT',
                           'statement': 'Entirely invented app, timestamp and values, not observed from any user or service.'},
            'source_url': 'synthetic://matched-evidence-v1/snapshot'}


def build():
    notes = {'parts': doc_note('MAX_FORM_PARTS', '``1_000``', '1000'),
             'memory': doc_note('MAX_FORM_MEMORY_SIZE', '``500_000``', '500000'),
             'root': doc_note('APPLICATION_ROOT', "``'/'``", '"/"'),
             'scheme': doc_note('PREFERRED_URL_SCHEME', "``'http'``", '"http"')}
    families = [
        ('d01', 'documentation', 'numeric', 'MAX_FORM_PARTS', '1000',
         'According to the documentation note, what is the default MAX_FORM_PARTS value?',
         '根据文档说明，MAX_FORM_PARTS 的默认值是多少？', notes['parts'], notes['memory'], '7'),
        ('d02', 'documentation', 'nonnumeric', 'APPLICATION_ROOT', '/',
         'According to the documentation note, what is the default APPLICATION_ROOT value?',
         '根据文档说明，APPLICATION_ROOT 的默认值是什么？', notes['root'], notes['scheme'], '"/orchid"'),
        ('r01', 'synthetic_runtime', 'numeric', 'MAX_FORM_PARTS', '7',
         f'In the invented snapshot, what is the effective MAX_FORM_PARTS value for app Orchid at {STAMP}?',
         f'在虚构快照中，应用 Orchid 在 {STAMP} 的 MAX_FORM_PARTS 有效配置值是多少？', notes['parts'], notes['parts'], '7'),
        ('r02', 'synthetic_runtime', 'nonnumeric', 'APPLICATION_ROOT', '/orchid',
         f'In the invented snapshot, what is the effective APPLICATION_ROOT value for app Orchid at {STAMP}?',
         f'在虚构快照中，应用 Orchid 在 {STAMP} 的 APPLICATION_ROOT 有效配置值是什么？', notes['root'], notes['root'], '"/orchid"'),
    ]
    cases = []
    for index, (fid, scope, kind, setting, expected, en, zh, positive, negative, runtime) in enumerate(families):
        for lang, query in [('en', en), ('zh', zh)]:
            order = ['sufficient', 'insufficient'] if (index + (lang == 'zh')) % 2 == 0 else ['insufficient', 'sufficient']
            for label in order:
                sufficient = label == 'sufficient'
                doc = positive if sufficient else negative
                subject = 'Orchid' if scope == 'synthetic_runtime' and sufficient else 'Willow'
                spans = [dict(doc, span_id=1), dict(snapshot(subject, setting, runtime), span_id=2)]
                cases.append({'id': fid + '-' + lang + '-' + label, 'pair_id': fid + '-' + lang,
                              'family': fid, 'scope': scope, 'answer_kind': kind, 'language': lang,
                              'query': query, 'condition': label, 'offered_sufficient': sufficient,
                              'supporting_span_ids': [1 if scope == 'documentation' else 2] if sufficient else [],
                              'assistant_expected_answer': expected if sufficient else None,
                              'assistant_evidence_basis': ('The relevant documentation note gives the requested default.' if scope == 'documentation' and sufficient else
                                  'The related note is for a different setting; the snapshot gives effective state, not the requested documented default.' if scope == 'documentation' else
                                  'The invented snapshot exactly matches the named app, timestamp and setting.' if sufficient else
                                  'Only another app snapshot is supplied; general documented defaults do not establish the named app effective value.'),
                              'spans': spans,
                              'generator_arm_order': ['legacy', 'branched'] if (index + (lang == 'zh') + sufficient) % 2 else ['branched', 'legacy']})
    return {'schema_version': 1, 'base_commit': BASE,
            'scope': 'AI-authored controlled development fixture; synthetic snapshots are not real telemetry. Four question families, eight bilingual question pairs, not a document holdout.',
            'cases': cases}


if __name__ == '__main__':
    (HERE / 'cases.json').write_text(json.dumps(build(), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
