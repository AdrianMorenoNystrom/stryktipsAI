import argparse
import json
import logging
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.stryktipset.service import DrawService
from app.stryktipset.provider import ProviderUnavailable
from app.stryktipset.parser import ProviderSchemaError


def main():
    parser=argparse.ArgumentParser(description="Read-only public coupon + crowd ingestion")
    parser.add_argument('--draw',type=int)
    parser.add_argument('--force',action='store_true',help='Explicitly fetch again, respecting HTTP rate limits')
    parser.add_argument('--due',action='store_true',help='Fetch only when configured snapshot policy is due')
    args=parser.parse_args()
    logging.basicConfig(level=logging.INFO,format='%(levelname)s %(message)s')
    service=DrawService()
    try:
        report=service.current(draw_number=args.draw) if args.due else service.ingest(args.draw,args.force)
        print(json.dumps(report,indent=2,ensure_ascii=False))
    except (ProviderUnavailable,ProviderSchemaError) as exc:
        print(json.dumps({'error':str(exc),'health':service.repo.health()}))
        raise SystemExit(1)


if __name__=='__main__': main()
