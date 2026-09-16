"""Scheduler-neutral, partially committing collection, independent of browser traffic."""
import json
import logging
from time import monotonic
from uuid import uuid4
from app.storage import iso, now_utc
from app.stryktipset.service import DrawService, choose_current, DrawNotReady
from app.stryktipset.provider import ProviderUnavailable
from app.stryktipset.parser import ProviderSchemaError


def collect(service=None, force=False):
    service = service or DrawService()
    repo = service.repo
    with repo.lock('collection') as acquired:
        if not acquired:
            return {'status':'busy'}
        started = now_utc()
        timer = monotonic()
        run = {'run_id':uuid4().hex, 'started_at':iso(started), 'completed_at':None, 'draw_number':None,
            'crowd_status':'not_due','market_status':'not_due','prediction_status':'not_due','optimizer_status':'not_due',
            'result_status':[], 'errors':[]}
        def save():
            with repo.connection() as con:
                con.execute('INSERT INTO collection_runs VALUES (?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET completed_at=excluded.completed_at,draw_number=excluded.draw_number,payload=excluded.payload',
                    (run['run_id'],run['started_at'],run['completed_at'],run['draw_number'],json.dumps(run)))
        save()
        try:
            draw = choose_current(repo.draws(), started)
            last = repo.health(service.provider_base + '/draws') if hasattr(service,'provider_base') else repo.health('https://api.spela.svenskaspel.se/draw/1/stryktipset/draws')
            from datetime import datetime
            last_time = datetime.fromisoformat(last['last_attempt']) if last['last_attempt'] else None
            interval = service.config.interval(started, draw.sales_close_at if draw else None)
            if last['status'] != 'Healthy':
                interval = min(interval, service.config.failure_retry_seconds)
            due = force or not last_time or (started-last_time).total_seconds() >= interval
            if due:
                try:
                    fetched = service.ingest(force=True)
                    run['crowd_status'] = 'saved' if fetched.get('updated') else 'skipped'
                except (ProviderUnavailable,ProviderSchemaError) as exc:
                    run['crowd_status'] = 'failed'
                    run['errors'].append(str(exc))
                draw = choose_current(repo.draws(),now_utc())
                if draw:
                    run['draw_number'] = draw.draw_number
                    market = service.market.update(draw)
                    run['market_status'] = market
                    run['errors'].extend(market.get('errors',[]))
                    save()  # Crowd survives an odds outage.
                    try:
                        result = service.analyze_live(draw.draw_number)
                        reused = result.get('reusedSnapshot', False)
                        run['prediction_status'] = {'saved':0 if reused else 13, 'reused':reused, 'snapshot_set':result['snapshotId']}
                        run['optimizer_status'] = {'saved':0 if reused else 1, 'reused':reused, 'snapshot_id':result['snapshotId'], 'budget':256,'profile':'optimal'}
                    except DrawNotReady as exc:
                        run['prediction_status'] = run['optimizer_status'] = 'incomplete_inputs'
                        run['errors'].append(str(exc))
            elif draw:
                run['draw_number'] = draw.draw_number
            # Results run independently of whether pre-match ingestion is due.
            for closed in repo.draws():
                actual = repo.result(closed.draw_number)
                if closed.sales_close_at <= now_utc() and not (actual and actual['completed']):
                    try:
                        result = service.update_results(closed.draw_number)
                        run['result_status'].append({'draw':closed.draw_number,'completed':result['completed']})
                    except (DrawNotReady,ProviderUnavailable,ProviderSchemaError) as exc:
                        run['errors'].append(f'Result draw {closed.draw_number}: {exc}')
            run['status'] = 'partial' if run['errors'] else 'completed'
        except Exception:
            run['status'] = 'failed'
            run['errors'].append('Internal collection error; inspect server diagnostics.')
            raise
        finally:
            run['completed_at'] = iso(now_utc())
            run['duration_seconds'] = round(monotonic()-timer,3)
            save()
            logging.getLogger(__name__).info(json.dumps(run))
        return run
