"""Record a launch check against an actual API and its database; no fixture odds."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.storage import iso, now_utc
from app.stryktipset.config import DrawConfig
from app.stryktipset.repository import DrawRepository
from export_live_dataset import TABLES


def verify(api):
    repo=DrawRepository(DrawConfig().root)
    with httpx.Client(base_url=api, timeout=60, headers={'Origin':'https://example.github.io'}) as client:
        health=client.get('/health'); health.raise_for_status()
        current=client.get('/api/coupon/current'); current.raise_for_status()
        state=current.json()
        assert state['analysis_ready'] and len(state['coupon']['matches'])==13
        response=client.post('/api/coupon/current/analyze',json={'drawNumber':state['draw']['draw_number'],'budget':256,'mode':'optimal'})
        response.raise_for_status()
        analysis=response.json()
        assert len(analysis['matches'])==13
        assert all(m['model']==m['market'] for m in analysis['matches'])
        assert client.get('/api/coupon/demo').status_code==404
        assert client.post('/api/teams/aliases',json={'alias':'launch-test','canonical':'Arsenal'}).status_code==403
        assert client.get('/api/teams/search',params={'q':'Arsenal'}).status_code==200
    with repo.connection() as con:
        counts={t:con.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0] for t in (*TABLES,'provider_raw_blobs')}
        migrations=[dict(r) for r in con.execute('SELECT version,checksum FROM schema_migrations ORDER BY version')]
        runs=[json.loads(r[0]) for r in con.execute('SELECT payload FROM collection_runs ORDER BY started_at')]
        raw=con.execute('SELECT id,content FROM provider_raw_blobs LIMIT 1').fetchone()
        assert raw and hashlib.sha256(bytes(raw[1])).hexdigest()==raw[0]
    return {'verified_at':iso(now_utc()),'deployment':'local production container and isolated Postgres; no public deployment',
        'health':health.json(),'database_engine':'postgres','migrations':migrations,'counts':counts,
        'draw':{k:state['draw'][k] for k in ('draw_number','sales_close_at','retrieved_at')},
        'mapping':state['mapping'],'sources':state['market_sources'],
        'matches':[{'number':m['number'],'home':m['homeTeam'],'away':m['awayTeam'],'market_source':m.get('marketSource'),
                    'bookmaker_count':(m.get('marketQuality') or {}).get('bookmaker_count',0),'probabilities':m['market']} for m in analysis['matches']],
        'active_model':'market','model_equals_market':True,'system':analysis['system'],'system_snapshot_id':analysis['snapshotId'],
        'raw_bytes_hash_verified':True,'production_demo_disabled':True,'shared_write_denied_without_token':True,
        'collection_runs':runs,'real_bookmaker_verification':'unavailable without configured credentials' if not counts['bookmaker_observations'] else 'observations present; inspect per-match coverage'}


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--api',default='http://127.0.0.1:8001')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    report=verify(args.api)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'draw':report['draw'],'counts':report['counts'],'output':str(args.output)},indent=2))
