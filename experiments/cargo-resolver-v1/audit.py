import argparse,json
from pathlib import Path
HERE=Path(__file__).resolve().parent
EXPECTED={'root-2021':'2','root-2024':'3','virtual-member-2024':'1','virtual-explicit-3':'3'}
def audit():
 d=json.loads((HERE/'cases.json').read_text())
 assert d['commit']=='d73d2caf9e41a39daf2a8d6ce60ec80bf354d2a7'
 assert d['license']=='MIT OR Apache-2.0'
 rows=[]
 for r in d['rows']:
  supported=r['id'] in EXPECTED and r['evidence_scope'] in ('root_package','virtual_root')
  rows.append({'id':r['id'],'gold':r['gold'],'supported':supported,'accepted_grounded':supported and r['gold']==EXPECTED.get(r['id'])})
 return {'source_commit':d['commit'],'rows':rows,'supported_rows':sum(x['supported'] for x in rows),'grounded_rows':sum(x['accepted_grounded'] for x in rows),'unsupported_rows':sum(not x['supported'] for x in rows)}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');args=p.parse_args();a=audit();out=json.dumps(a,ensure_ascii=False,sort_keys=True,indent=2)+'\n'
 if args.check: assert (HERE/'summary.json').read_text()==out
 else: print(out,end='')
