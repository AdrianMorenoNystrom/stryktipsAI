"""Idempotently copy a local Stryktipset archive into migrated Postgres, including raw bytes."""
import argparse
import json
from pathlib import Path
import sqlite3
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.database import migrate
from app.stryktipset.repository import DrawRepository
from app.stryktipset.config import DrawConfig
from export_live_dataset import TABLES

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--source',type=Path,required=True)
    args=parser.parse_args()
    target=DrawRepository(DrawConfig().root)
    if not target.database_url:raise SystemExit('DATABASE_URL is required; source is always read-only SQLite.')
    migrate()
    source=sqlite3.connect(args.source.resolve().as_uri()+'?mode=ro',uri=True);source.row_factory=sqlite3.Row
    available={r[0] for r in source.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    raw_map={}
    for table,column in [('provider_raw_payloads','raw_path'),('odds_requests','raw_reference')]:
        if table not in available:continue
        for row in source.execute(f'SELECT DISTINCT {column} FROM {table} WHERE {column} IS NOT NULL'):
            raw_map[row[0]]=target.save_raw((args.source.parent/row[0]).read_bytes())
    def rewrite(value):
        if isinstance(value,dict):return {k:rewrite(v) for k,v in value.items()}
        if isinstance(value,list):return [rewrite(v) for v in value]
        return raw_map.get(value,value) if isinstance(value,str) else value
    counts={}
    with target.connection() as con:
        for table in (*TABLES,'provider_health'):
            if table not in available:continue
            counts[table]=0
            for row in source.execute(f'SELECT * FROM {table}'):
                item=dict(row)
                if 'payload' in item:item['payload']=json.dumps(rewrite(json.loads(item['payload'])),ensure_ascii=False)
                for column in ('raw_path','raw_reference'):
                    if item.get(column):item[column]=raw_map[item[column]]
                columns=','.join(item)
                inserted=con.execute(f"INSERT OR IGNORE INTO {table} ({columns}) VALUES ({','.join('?' for _ in item)})",tuple(item.values())).rowcount
                counts[table]+=inserted
    print(json.dumps({'inserted':counts,'destination':'postgres'},indent=2))
