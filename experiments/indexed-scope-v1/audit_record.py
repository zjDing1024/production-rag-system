"""Offline replay of actual BM25, routing, packing and disclosed spy calls."""
import argparse
import json
from pathlib import Path
from run_experiment import HERE, execute, sha, summarize, verify_freeze
from rag_foundation.corpus import canonical_json
from rag_foundation.generation import strict_json
from build_fixture import build
from build_english_correction import build_correction


def audit(directory=HERE):
    lock=verify_freeze(directory)
    expected=lock['sha256']['experiments/indexed-scope-v1/cases.json']
    if sha(directory/'cases.json')!=expected:raise ValueError('case fixture changed')
    if strict_json((directory/'cases.json').read_text(encoding='utf-8'))!=build():raise ValueError('fixture rebuild mismatch')
    index=strict_json((directory/'recorded.sha256.json').read_text(encoding='utf-8'))
    if set(index)!={'recorded.json'} or sha(directory/'recorded.json')!=index['recorded.json']:
        raise ValueError('recorded checksum mismatch')
    actual=strict_json((directory/'recorded.json').read_text(encoding='utf-8'))
    replay=execute(directory)
    if actual!=replay:raise ValueError('pipeline replay mismatch')
    return summarize(actual)


def audit_correction(directory=HERE):
    folder=directory/'english-correction'
    lock=verify_freeze(folder)
    if sha(folder/'cases.json')!=lock['sha256']['experiments/indexed-scope-v1/english-correction/cases.json']:
        raise ValueError('corrected fixture changed')
    if strict_json((folder/'cases.json').read_text(encoding='utf-8'))!=build_correction():
        raise ValueError('corrected fixture rebuild mismatch')
    index=strict_json((folder/'recorded.sha256.json').read_text(encoding='utf-8'))
    if set(index)!={'recorded.json'} or sha(folder/'recorded.json')!=index['recorded.json']:
        raise ValueError('corrected record checksum mismatch')
    record=strict_json((folder/'recorded.json').read_text(encoding='utf-8'))
    if record!=execute(folder):raise ValueError('corrected pipeline replay mismatch')
    return summarize(record)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--check',action='store_true');args=parser.parse_args()
    value=audit()
    if args.check:
        if value!=strict_json((HERE/'summary.json').read_text(encoding='utf-8')):raise ValueError('summary mismatch')
        if audit_correction()!=strict_json((HERE/'english-correction/summary.json').read_text(encoding='utf-8')):raise ValueError('correction summary mismatch')
        print('Original indexed-scope record and explicit English correction match offline pipeline replay.')
    else:print(canonical_json(value),end='')
