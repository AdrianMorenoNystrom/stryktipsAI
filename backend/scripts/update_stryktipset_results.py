import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.storage import now_utc
from app.stryktipset.service import DrawService,DrawNotReady
from app.stryktipset.provider import ProviderUnavailable
from app.stryktipset.parser import ProviderSchemaError


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--draw',type=int)
    parser.add_argument('--force',action='store_true')
    args=parser.parse_args()
    service=DrawService()
    numbers=[args.draw] if args.draw else [d.draw_number for d in service.repo.draws() if d.sales_close_at<=now_utc() and not (service.repo.result(d.draw_number) or {}).get('completed')]
    report={'updated':[],'failed':[]}
    for n in numbers:
        try:
            result=service.update_results(n,args.force)
            report['updated'].append({'draw':n,'completed':result['completed'],'matches':len(result['matches']),'payouts':len(result['payouts'])})
        except (DrawNotReady,ProviderUnavailable,ProviderSchemaError) as exc:
            report['failed'].append({'draw':n,'error':str(exc)})
    print(json.dumps(report,indent=2))


if __name__=='__main__': main()
