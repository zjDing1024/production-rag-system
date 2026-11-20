"""Original short reviewed summaries from pinned CPython/Express source oracles."""
from dataclasses import asdict
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'src'))
from rag_foundation.corpus import Chunk,canonical_json,digest
from rag_foundation.scope_gate import Scope
from rag_foundation.scoped_pipeline import chunks_fingerprint

HERE=Path(__file__).resolve().parent


def record(name,subject,version,key,value,text,source_id,lines):
    scope=Scope('documentation',subject,key,version=version)
    text_hash=digest(text.encode())
    chunk=Chunk(name,'authored-'+name,'Original source summary',text,
                'authored-summary://source-transfer-v1/'+name,text_hash,'MIT',0,len(text),1,1)
    entry={'chunk_id':name,'scope':asdict(scope),'claim':{'reviewed':True,'chunk_text_sha256':text_hash,
           'value_type':'string','unit':'canonical_literal','value':value,'start_char':0,'end_char':len(text),'quote':text}}
    sources={s['source_id']:s for s in json.loads((HERE/'source-manifest.json').read_text())};source=sources[source_id]
    ref={'source_id':source_id,'upstream_sha256':source['sha256'],'upstream_url':
         f"https://github.com/{source['repository']}/blob/{source['revision']}/{source['path']}#L{lines[0]}-L{lines[1]}",
         'authored_summary_not_verbatim':True}
    return chunk,entry,ref


def build():
    rows={}
    def add(name,*args):rows[name]=record(name,*args)
    add('p14default','CPython','3.14.0','ArgumentParser.suggest_on_error.default','False',
        'CPython 3.14.0: the ArgumentParser constructor parameter suggest_on_error has the default False.',
        'cpython314-Lib_argparse.py',(1880,1880))
    add('p14explicit','CPython','3.14.0','ArgumentParser.suggest_on_error.explicit_example','True',
        'CPython 3.14.0: a usage test explicitly constructs ArgumentParser with suggest_on_error=True. This is an explicit example setting, not a statement of the constructor default.',
        'cpython314-Lib_test_test_argparse.py',(2288,2296))
    add('p14color','CPython','3.14.0','ArgumentParser.color.default','True',
        'CPython 3.14.0: the ArgumentParser constructor parameter color has the default True.',
        'cpython314-Lib_argparse.py',(1881,1881))
    add('p13presence','CPython','3.13.0','ArgumentParser.suggest_on_error.parameter_presence','absent',
        'CPython 3.13.0: the complete ArgumentParser constructor signature does not contain a suggest_on_error parameter. Its parameter presence is absent, not a Boolean default value.',
        'cpython313-Lib_argparse.py',(1750,1765))
    add('p14presence','CPython','3.14.0','ArgumentParser.suggest_on_error.parameter_presence','present',
        'CPython 3.14.0: suggest_on_error is present as a named ArgumentParser constructor parameter. This summary states presence only.',
        'cpython314-Lib_argparse.py',(1877,1881))
    add('p13abbrev','CPython','3.13.0','ArgumentParser.allow_abbrev.default','True',
        'CPython 3.13.0: the ArgumentParser constructor parameter allow_abbrev has the default True.',
        'cpython313-Lib_argparse.py',(1762,1765))
    add('e4default','Express','4.21.2','query parser.default','extended',
        'Express 4.21.2 initializes the query parser application setting to extended by default.',
        'express421-lib_application.js',(80,86))
    add('e5default','Express','5.1.0','query parser.default','simple',
        'Express 5.1.0 initializes the query parser application setting to simple by default.',
        'express510-lib_application.js',(93,100))
    add('e5explicit','Express','5.1.0','query parser.explicit_example','extended',
        'Express 5.1.0: a test explicitly sets the query parser application setting to extended. This is an explicit example setting, not a statement of the default.',
        'express510-test_req.query.js',(24,31))
    add('e5trust','Express','5.1.0','trust proxy.default','False',
        'Express 5.1.0 initializes the trust proxy application setting to false by default. This summary concerns trust proxy only.',
        'express510-lib_application.js',(99,99))
    rows['e5explicit'][2]['additional_upstream_urls']=['https://github.com/expressjs/express/blob/cd7d4397c398a3f3ecadeaf9ef6ac1377bd414c4/test/req.query.js#L94-L99']
    definitions=[
      ('py-default-supported','argparse.suggest_on_error','py314-suggest-default','p14default',['p14explicit','p14default'],True,'False',
       'In CPython 3.14.0, what is the ArgumentParser constructor default for suggest_on_error?',
       '在 CPython 3.14.0 中， ArgumentParser 构造函数的 suggest_on_error 默认值是什么？'),
      ('py-default-older-only','argparse.suggest_on_error','py314-suggest-default','p14default',['p13presence'],False,'False',None,None),
      ('py-default-explicit-only','argparse.suggest_on_error','py314-suggest-default','p14default',['p14explicit'],False,'False',None,None),
      ('py-default-near-field','argparse.suggest_on_error','py314-suggest-default','p14default',['p14color'],False,'False',None,None),
      ('py-absence-supported','argparse.suggest_on_error','py313-suggest-presence','p13presence',['p14presence','p13presence'],True,'absent',
       'In CPython 3.13.0, is suggest_on_error present or absent in the complete ArgumentParser constructor signature?',
       '在 CPython 3.13.0 的完整 ArgumentParser 构造函数签名中， suggest_on_error 参数是 present 还是 absent？'),
      ('py-abbrev-supported','argparse.allow_abbrev','py313-abbrev-default','p13abbrev',['p14default','p13abbrev'],True,'True',
       'In CPython 3.13.0, what is the ArgumentParser constructor default for allow_abbrev?',
       '在 CPython 3.13.0 中， ArgumentParser 构造函数的 allow_abbrev 默认值是什么？'),
      ('express-old-supported','express.query_parser','express421-query-default','e4default',['e5default','e4default'],True,'extended',
       'In Express 4.21.2, what is the exact default value of the query parser application setting?',
       '在 Express 4.21.2 中， query parser 应用设置的确切默认值是什么？'),
      ('express-new-supported','express.query_parser','express510-query-default','e5default',['e4default','e5default'],True,'simple',
       'In Express 5.1.0, what is the exact default value of the query parser application setting?',
       '在 Express 5.1.0 中， query parser 应用设置的确切默认值是什么？'),
      ('express-new-older-only','express.query_parser','express510-query-default','e5default',['e4default'],False,'simple',None,None),
      ('express-new-explicit-only','express.query_parser','express510-query-default','e5default',['e5explicit'],False,'simple',None,None),
      ('express-new-near-field','express.query_parser','express510-query-default','e5default',['e5trust'],False,'simple',None,None)]
    queries={};cases=[]
    for i,(cid,family,target,correct,names,sufficient,gold,en,zh) in enumerate(definitions):
        if en:queries[target]=(en,zh)
        for lang,query in zip(('en','zh'),queries[target]):
            chunks=[rows[n][0] for n in names];entries=[rows[n][1] for n in names]
            scope=rows[correct][1]['scope'];support=[correct] if sufficient else []
            cases.append({'id':cid+'-'+lang,'condition_id':cid,'source_family':'CPython' if cid.startswith('py-') else 'Express',
                'fact_family':family,'release_specific_target':target,'language':lang,
                'request':{'query':query,'scope':scope},'chunks':[asdict(c) for c in chunks],
                'catalog':{'schema_version':1,'complete':True,'chunks_sha256':chunks_fingerprint(chunks),'entries':entries},
                'source_refs':{n:rows[n][2] for n in names},'options':{'k':1,'context_characters':12000,'scan_limit':128},
                'arm_order':['ungated','scoped'] if (i+(lang=='zh'))%2==0 else ['scoped','ungated'],
                'rubric':{'offered_sufficient':sufficient,'supporting_ids':support,'external_gold':gold,
                    'literal_forms':{'False':['False','false'],'True':['True','true']}.get(gold,[gold]),
                    'typed_requirement':'Canonical string for the requested predicate. False is neither 0, null nor absent; explicit setting is not default.',
                    'scope_query_agreement':'AI reviewed fixture invariant, not a product scope inference capability'}})
    return {'schema_version':1,'study':'source-transfer-v1','source_families':2,'setting_fact_families':3,
            'release_specific_targets':5,'conditions':11,'rows':len(cases),'cases':cases}


if __name__=='__main__':print(canonical_json(build()),end='')
