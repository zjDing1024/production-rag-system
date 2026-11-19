"""Run only the separately frozen English input correction with the original runner."""
import argparse
from pathlib import Path
from run_experiment import HERE, execute, summarize
from rag_foundation.corpus import canonical_json

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    record=execute(HERE/'english-correction')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf-8') as stream:stream.write(canonical_json(record))
    print(canonical_json(summarize(record)),end='')
