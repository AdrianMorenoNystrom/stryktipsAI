import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.stryktipset.teams import save_alias

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('alias')
    parser.add_argument('canonical')
    args=parser.parse_args()
    print(json.dumps(save_alias(args.alias,args.canonical),ensure_ascii=False))
