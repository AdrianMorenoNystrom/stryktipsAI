"""Bounded, resumable public history import; never backdates crowd/odds observations."""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.stryktipset.service import DrawService,DrawNotReady
from app.stryktipset.provider import ProviderUnavailable
from app.stryktipset.parser import ProviderSchemaError


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--from-draw',type=int,required=True)
    parser.add_argument('--to-draw',type=int,required=True)
    parser.add_argument('--refresh',action='store_true')
    args=parser.parse_args()
    service=DrawService()
    if args.from_draw<1 or not 0<=args.to_draw-args.from_draw<service.config.max_import_draws:
        raise SystemExit(f'Use an ascending range of at most {service.config.max_import_draws} draws.')
    report={'from_draw':args.from_draw,'to_draw':args.to_draw,'draws':[],'failed':[],'historical_pre_close_observations_created':0}
    path=service.config.root/f'history_import_{args.from_draw}_{args.to_draw}.json'
    for n in range(args.from_draw,args.to_draw+1):
        try:
            ingested=service.ingest(n,args.refresh)
            draw=service.repo.draw(n)
            result=service.update_results(n,args.refresh)
            row={'draw_number':n,'date':str(draw.draw_date),'matches':len(draw.matches),'crowd_matches':sum(m.crowd is not None for m in draw.matches),
                'result_matches':sum(m['outcome'] is not None for m in result['matches']),'payout_levels':len(result['payouts']),'cached':not ingested['updated']}
            report['draws'].append(row)
            print(json.dumps(row),flush=True)
        except (DrawNotReady,ProviderUnavailable,ProviderSchemaError) as exc:
            report['failed'].append({'draw_number':n,'error':str(exc)})
        path.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(path)


if __name__=='__main__': main()
