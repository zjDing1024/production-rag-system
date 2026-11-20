"""Optional pinned public-source verification; no network unless --fetch is supplied."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import urllib.request

HERE=Path(__file__).resolve().parent


def verify(fetch=False,directory=None):
    manifest=HERE/'source-manifest.json';lock=json.loads((HERE/'cases.lock.json').read_text())
    if hashlib.sha256(manifest.read_bytes()).hexdigest()!=lock['file_sha256']['experiments/source-transfer-v1/source-manifest.json']:
        raise ValueError('frozen source receipt changed')
    rows=json.loads(manifest.read_text());checks=[]
    if fetch:
        directory=Path(directory or '/tmp/rag-source-oracles').resolve()
        if not directory.is_relative_to('/tmp'):raise ValueError('keep optional public oracle downloads under /tmp')
        if directory.is_relative_to(HERE.parents[1]):raise ValueError('oracle files must stay outside the repository')
        directory.mkdir(parents=True,exist_ok=True)
    for r in rows:
        if not fetch:
            checks.append({'source_id':r['source_id'],'status':'not_fetched','expected_sha256':r['sha256']});continue
        if not r['url'].startswith(('https://raw.githubusercontent.com/python/cpython/','https://raw.githubusercontent.com/expressjs/express/')):
            raise ValueError('not an approved public source prefix')
        with urllib.request.urlopen(r['url'],timeout=45) as response:data=response.read(4_000_001)
        if len(data)>4_000_000 or len(data)!=r['bytes'] or hashlib.sha256(data).hexdigest()!=r['sha256']:
            raise ValueError('pinned public source mismatch')
        (directory/r['source_id']).write_bytes(data)
        checks.append({'source_id':r['source_id'],'status':'verified_public_bytes','sha256':r['sha256']})
    oracle=[]
    if fetch:
        for name in ('cpython313','cpython314'):
            tree=ast.parse((directory/(name+'-Lib_argparse.py')).read_text())
            cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='ArgumentParser')
            init=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='__init__')
            values=dict(zip([a.arg for a in init.args.args][-len(init.args.defaults):],init.args.defaults))
            values.update(zip([a.arg for a in init.args.kwonlyargs],init.args.kw_defaults))
            found={key:ast.literal_eval(values[key]) if key in values else 'PARAMETER_ABSENT' for key in ('allow_abbrev','suggest_on_error','color')}
            assert found['allow_abbrev'] is True
            if name=='cpython314':assert found['suggest_on_error'] is False and found['color'] is True
            else:assert found['suggest_on_error']=='PARAMETER_ABSENT' and found['color']=='PARAMETER_ABSENT'
            oracle.append({'source':name,'method':'AST-only, no upstream code executed','values':found})
    return {'network_requested':fetch,'source_checks':checks,'cpython_static_oracle':oracle}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--fetch',action='store_true');parser.add_argument('--directory',type=Path);args=parser.parse_args()
    print(json.dumps(verify(args.fetch,args.directory),indent=2))
