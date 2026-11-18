"""Original fixture construction. No web request and no private runtime data."""
from copy import deepcopy
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = '68464ade084abe7251a6af4cc17ebf28f6700466'
KEY = 'SEND_FILE_MAX_AGE_DEFAULT'
STAMP = '2032-07-08T09:00:00Z'


def scope(kind, subject, key, version=None, observed_at=None):
    return dict(kind=kind, subject=subject, key=key, version=version, observed_at=observed_at)


def doc(version):
    source = next(s for s in json.loads((HERE / 'sources/manifest.json').read_text()) if s['version'] == version)
    value = source['verified_documented_value']
    text = (f'Original documentation summary\nProject: Flask\nVersion: {version}\nSetting: {KEY}\n'
            f'Documented default: {value:<5}\nNumeric values are in seconds; None is a literal configuration value.\n'
            'This is a documented default, not an observed application state.\n')
    return {'scope': scope('documentation', 'Flask', KEY, version), 'text': text,
            'citation': f"https://github.com/pallets/flask/blob/{source['revision']}/docs/config.rst#L{source['line_start']}",
            'source_identity': 'flask-' + version, 'value': value}


def runtime(subject, at, key, value):
    return {'scope': scope('runtime', subject, key, observed_at=at),
            'text': f'Invented runtime snapshot, not real telemetry\nApplication: {subject}\nObserved at: {at}\nSetting: {key}\nEffective value: {value}\n',
            'citation': 'synthetic://typed-scope-v1/snapshot',
            'source_identity': f'synthetic-{subject}-{at}-{key}', 'value': value}


def build():
    groups = [
        ('v_old','version_default',scope('documentation','Flask',KEY,'1.1.4'),
         'According to Flask 1.1.4 documentation, what is the default SEND_FILE_MAX_AGE_DEFAULT in seconds?',
         '根据 Flask 1.1.4 文档，SEND_FILE_MAX_AGE_DEFAULT 的默认秒数是多少？',
         [doc('1.1.4'),doc('3.1.2')],[doc('3.1.0'),doc('3.1.2')],0,'43200'),
        ('v_new','version_default',scope('documentation','Flask',KEY,'3.1.2'),
         'According to Flask 3.1.2 documentation, what is the default value of SEND_FILE_MAX_AGE_DEFAULT?',
         '根据 Flask 3.1.2 文档，SEND_FILE_MAX_AGE_DEFAULT 的默认值是什么？',
         [doc('1.1.4'),doc('3.1.2')],[doc('1.1.4'),doc('3.1.0')],1,'None'),
        ('entity','synthetic_timeout',scope('runtime','Cedar','request_timeout_seconds',observed_at=STAMP),
         f'In the invented snapshot, what is the request_timeout_seconds value for Cedar at {STAMP}?',
         f'在虚构快照中，Cedar 在 {STAMP} 的 request_timeout_seconds 值是多少？',
         [runtime('Cedar',STAMP,'request_timeout_seconds','17'),runtime('Birch',STAMP,'request_timeout_seconds','23')],
         [runtime('Maple',STAMP,'request_timeout_seconds','17'),runtime('Birch',STAMP,'request_timeout_seconds','23')],0,'17'),
        ('time','synthetic_route',scope('runtime','Cedar','health_route',observed_at=STAMP),
         f'In the invented snapshot, what is the exact health_route value for Cedar at {STAMP}?',
         f'在虚构快照中，Cedar 在 {STAMP} 的 health_route 精确值是什么？',
         [runtime('Cedar','2032-07-08T08:00:00Z','health_route','/ready-old'),runtime('Cedar',STAMP,'health_route','/ready-new')],
         [runtime('Cedar','2032-07-08T08:00:00Z','health_route','/ready-old'),runtime('Cedar','2032-07-08T07:00:00Z','health_route','/ready-new')],1,'/ready-new'),
    ]
    cases=[]
    for gi,(group,fact,requested,en,zh,positive,negative,gold_index,expected) in enumerate(groups):
        for lang,query in [('en',en),('zh',zh)]:
            for order in (0,1):
                for ids in (0,1):
                    layout=f'o{order}i{ids}'
                    conds=['sufficient','insufficient'] if (gi+order+ids+(lang=='zh'))%2==0 else ['insufficient','sufficient']
                    for condition in conds:
                        sufficient=condition=='sufficient'
                        candidates=deepcopy(positive if sufficient else negative)
                        idmap=['q7','m2'] if ids==0 else ['m2','q7']
                        for i,r in enumerate(candidates):r['record_id']=idmap[i]
                        identities={r['record_id']:r['source_identity'] for r in candidates}
                        if order:candidates.reverse()
                        records=[{k:r[k] for k in ('record_id','scope','text','citation')} for r in candidates]
                        cases.append({'id':f'{group}-{lang}-{layout}-{condition}','group':group,'fact_family':fact,
                            'pair_id':f'{group}-{lang}-{layout}','language':lang,'layout':layout,
                            'condition':condition,'input':{'query':query,'scope':requested,'records':records},
                            'source_identities':identities,'offered_sufficient':sufficient,
                            'supporting_ids':[idmap[gold_index]] if sufficient else [],
                            'expected_value':expected if sufficient else None,
                            'scope_matches_question':'AI-authored and second-AI-reviewed fixture invariant only; not inferred by the gate.',
                            'arm_order':['ungated','gated'] if (gi+order+ids+(lang=='zh')+sufficient)%2 else ['gated','ungated']})
    return {'schema_version':1,'base_commit':BASE,'description':'64 controlled rows: 4 request groups / 3 fact families, EN+ZH, sufficient+insufficient, independent 2x2 display-order and opaque-ID permutations. Synthetic records are invented; metadata is trusted fixture input.', 'cases':cases}


if __name__ == '__main__':
    (HERE/'cases.json').write_text(json.dumps(build(),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
