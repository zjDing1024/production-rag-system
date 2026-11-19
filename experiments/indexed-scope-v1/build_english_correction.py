"""Post-discovery input repair, not a changed pipeline or scoring threshold."""
from dataclasses import asdict
from build_fixture import build
from rag_foundation.corpus import Chunk, digest, canonical_json
from rag_foundation.scoped_pipeline import chunks_fingerprint


def build_correction():
    cases=[]
    for original in build()['cases']:
        if not original['id'].startswith('zero-en-'):continue
        c=original
        c['id']=c['id'].replace('zero-en-','corrected-en-')
        text=c['chunks'][1]['text'].replace('The configured duration is ','Configured duration: ')
        c['chunks'][1].update(text=text,end_char=len(text),source_sha256=digest(text.encode()))
        c['catalog']['entries'][1]['claim'].update(chunk_text_sha256=digest(text.encode()),end_char=len(text),quote=text)
        c['catalog']['chunks_sha256']=chunks_fingerprint([Chunk(**r) for r in c['chunks']])
        cases.append(c)
    return {'schema_version':1,'study':'indexed-scope-v1-english-correction','cases':cases}


if __name__=='__main__':print(canonical_json(build_correction()),end='')
