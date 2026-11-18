"""Optional public-source recheck. No network unless --fetch is explicitly supplied."""
import argparse
import hashlib
import json
from pathlib import Path
import urllib.request

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]


def bounded_download(url):
    if not url.startswith('https://raw.githubusercontent.com/pallets/flask/'):
        raise ValueError('only pinned public Pallets Flask sources are allowed')
    with urllib.request.urlopen(url,timeout=45) as response:
        value=response.read(262145)
    if len(value)>262144:raise ValueError('source exceeds byte bound')
    return value


def verify(fetch=False):
    manifest=HERE/'sources/manifest.json'
    lock=json.loads((HERE/'cases.lock.json').read_text())
    if hashlib.sha256(manifest.read_bytes()).hexdigest()!=lock['file_sha256']['experiments/typed-scope-v1/sources/manifest.json']:
        raise ValueError('source manifest changed after freeze')
    rows=[]
    for source in json.loads(manifest.read_text()):
        local=source.get('local_source')
        if not fetch and not local:
            rows.append({'version':source['version'],'status':'not_fetched','source_sha256':source['source_sha256']})
            continue
        value=(REPO/local).read_bytes() if local and not fetch else bounded_download(source['source_url'])
        if hashlib.sha256(value).hexdigest()!=source['source_sha256']:raise ValueError('whole-source hash mismatch')
        excerpt=value.decode('utf-8')[source['char_start']:source['char_end']].encode('utf-8')
        if hashlib.sha256(excerpt).hexdigest()!=source['excerpt_sha256']:raise ValueError('excerpt hash mismatch')
        if fetch and 'license_url' in source:
            license_value=bounded_download(source['license_url'])
            if hashlib.sha256(license_value).hexdigest()!=source['license_sha256']:raise ValueError('license hash mismatch')
        rows.append({'version':source['version'],'status':'verified_public_download' if fetch else 'verified_existing_local_corpus',
                     'source_sha256':source['source_sha256'],'excerpt_sha256':source['excerpt_sha256']})
    return {'network_requested':fetch,'source_checks':rows}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--fetch',action='store_true');args=parser.parse_args()
    print(json.dumps(verify(args.fetch),indent=2))
