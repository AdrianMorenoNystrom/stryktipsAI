import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.collection import collect
from app.runtime import Runtime

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--force',action='store_true')
    args=parser.parse_args()
    Runtime.load()
    print(json.dumps(collect(force=args.force),indent=2,ensure_ascii=False))
