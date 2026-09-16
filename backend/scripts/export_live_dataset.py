"""Consistent point-in-time JSONL export of durable input and outcome tables separately."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.storage import iso,now_utc
from app.stryktipset.config import DrawConfig
from app.stryktipset.repository import DrawRepository

TABLES=('stryktipset_draws','stryktipset_matches','draw_observations','crowd_snapshots','market_snapshots','consensus_snapshots','bookmaker_observations','prediction_snapshots','optimizer_snapshots','result_observations','match_results','draw_payouts','provider_raw_payloads','odds_requests','collection_runs')

def export(repo,destination):
    destination.mkdir(parents=True,exist_ok=False)
    counts={}
    with repo.connection() as con:
        con.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY' if repo.database_url else 'BEGIN')
        for table in TABLES:
            counts[table]=0
            with (destination/f'{table}.jsonl').open('w',encoding='utf-8') as stream:
                for row in con.execute(f'SELECT * FROM {table}'):
                    item=dict(row)
                    if 'payload' in item:item['payload']=json.loads(item['payload'])
                    stream.write(json.dumps(item,ensure_ascii=False)+'\n')
                    counts[table]+=1
    manifest={'export_time':iso(now_utc()),'schema_version':2,'database_engine':'postgres' if repo.database_url else 'sqlite',
        'draw_count':counts['stryktipset_draws'],'match_count':counts['stryktipset_matches'],
        'snapshot_count':sum(v for k,v in counts.items() if k.endswith('_snapshots')),'counts':counts,
        'raw_payload_note':'Raw references retained. Use pg_dump for a complete database backup including raw bytes.',
        'temporal_policy':'Inputs require recorded_at, retrieved_at and source_updated_at <= cutoff. Never backdate imported crowd.'}
    (destination/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    return manifest

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=Path('exports')/now_utc().strftime('%Y%m%dT%H%M%S%fZ'))
    args=parser.parse_args();print(json.dumps(export(DrawRepository(DrawConfig().root),args.output),indent=2))
