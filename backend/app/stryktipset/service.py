"""Live ingestion and point-in-time inputs around the existing analysis/optimizer."""
from datetime import datetime, timedelta
import hashlib
import logging
from threading import Lock
from app.config import ROW_COST
from app.schemas import AnalyzeRequest, Coupon, CouponMatch, Crowd, Odds, Snapshot
from app.services.coupon import analyze
from app.storage import iso, now_utc
from app.stryktipset.config import BASE_URL, STOCKHOLM, DrawConfig
from app.stryktipset.parser import ProviderSchemaError
from app.stryktipset.provider import ProviderUnavailable, SvenskaSpelProvider
from app.stryktipset.repository import DrawRepository, fixture_key
from app.stryktipset.schemas import Draw
from ml.predict import PredictionService
from app.market.service import MarketService

log = logging.getLogger(__name__)
INGEST_LOCK = Lock()


class DrawNotReady(ValueError):
    pass


def choose_current(draws: list[Draw], at: datetime) -> Draw | None:
    future = [d for d in draws if d.status in ("open","upcoming") and d.sales_close_at > at and not d.issues]
    opened = [d for d in future if d.status == "open" and (d.sales_open_at is None or d.sales_open_at <= at)]
    return min(opened or future,key=lambda d:(d.sales_close_at,d.draw_number),default=None)


def movements(history: list[dict]) -> dict:
    if len(history) < 2:
        return {"since_previous":None,"since_first":None,"observations":len(history)}
    return {"since_previous":{k:history[-1]['crowd'][k]-history[-2]['crowd'][k] for k in ('home','draw','away')},
            "since_first":{k:history[-1]['crowd'][k]-history[0]['crowd'][k] for k in ('home','draw','away')},"observations":len(history)}


class DrawService:
    def __init__(self, config=None, provider=None, predictor=None):
        self.config = config or DrawConfig()
        self.repo = DrawRepository(self.config.root)
        self.provider = provider or SvenskaSpelProvider(self.config,self.repo)
        self.predictor = predictor or PredictionService()
        self.market = MarketService(self.repo)

    def ingest(self, draw_number: int | None = None, force=False) -> dict:
        if not self.config.enabled:
            return {"updated":False,"disabled":True}
        if not INGEST_LOCK.acquire(blocking=False):
            return {"updated":False,"busy":True}
        try:
            with self.repo.lock('draw-ingest') as acquired:
                if not acquired:
                    return {"updated":False,"busy":True}
                if draw_number is not None:
                    saved = self.repo.draw(draw_number)
                    if saved and not force:
                        return {"updated":False,"cached":True,"draws":[draw_number]}
                    draws = [self.provider.get_draw(draw_number,refresh=force)]
                else:
                    draws = self.provider.get_current_draw(refresh=force)
                ids, diagnostics = [], []
                for draw in draws:
                    observation = self.repo.save_draw(draw,now_utc())
                    ids.append(observation)
                    movement = self.movement(draw.draw_number, now_utc())
                    diagnostics.append({'draw_number': draw.draw_number, 'mapping': self.mapping(draw), 'movement': movement})
                    log.info("Stryktipset draw=%s matches=%s crowd=%s mapped=%s observation=%s",draw.draw_number,len(draw.matches),sum(m.crowd is not None for m in draw.matches),sum(bool(i) for m in draw.matches for i in (m.home_team_id,m.away_team_id)),observation)
                return {"updated":True,"draws":[d.draw_number for d in draws],"observations":ids,"diagnostics":diagnostics,"counts":self.repo.counts()}
        finally:
            INGEST_LOCK.release()

    def current(self, refresh=False, draw_number=None) -> dict:
        at = now_utc()
        selected = self.repo.draw(draw_number) if draw_number is not None else choose_current(self.repo.draws(),at)
        source = BASE_URL + '/draws' + (f'/{draw_number}' if draw_number is not None else '')
        health = self.repo.health(source)
        last_attempt = datetime.fromisoformat(health['last_attempt']) if health['last_attempt'] else None
        cooldown = health['status'] != 'Healthy' and last_attempt and (at-last_attempt).total_seconds() < self.config.failure_retry_seconds
        elapsed = (at-selected.retrieved_at).total_seconds() if selected else float('inf')
        due = elapsed >= (self.config.manual_refresh_min_seconds if refresh else self.config.interval(at,selected.sales_close_at if selected else None))
        if last_attempt and (at-last_attempt).total_seconds() < self.config.manual_refresh_min_seconds:
            due = False
        failure = None
        if self.config.enabled and due and (refresh or not cooldown):
            try:
                self.ingest(draw_number,force=True)
                updated_draw = self.repo.draw(draw_number) if draw_number else choose_current(self.repo.draws(),now_utc())
                if updated_draw:
                    self.market.update(updated_draw)
            except (ProviderUnavailable,ProviderSchemaError) as exc:
                failure = str(exc)
            at = now_utc()
            selected = self.repo.draw(draw_number) if draw_number is not None else choose_current(self.repo.draws(),at)
        if selected and self.config.enabled and self.market.config.api_key and selected.sales_close_at > at:
            market_health = self.market.health()
            market_attempt = datetime.fromisoformat(market_health['last_attempt']) if market_health['last_attempt'] else None
            market_interval = min(self.config.interval(at, selected.sales_close_at), self.market.config.fresh_seconds)
            if not market_attempt or (at-market_attempt).total_seconds() >= market_interval:
                self.market.update(selected)
                at = now_utc()
        health = self.repo.health(source)
        if selected and not health['last_attempt']:
            health = self.repo.health(selected.source)
        if not selected:
            return {"draw":None,"coupon":None,"analysis_ready":False,"available_draws":[],"health":health,"stale":False,
                    "issues":[],"message":"Ingen aktuell livekupong kunde hämtas. DEMO DATA och manuell kupong finns tillgängliga.","enabled":self.config.enabled}
        coupon, issues, inputs = self.coupon_at(selected.draw_number,at)
        interval = self.config.interval(at,selected.sales_close_at)
        stale = bool(failure or health['status'] != 'Healthy' or (at-selected.retrieved_at).total_seconds() > interval)
        return {"draw":selected.model_dump(mode='json'),"coupon":coupon.model_dump(mode='json') if coupon else None,
            "analysis_ready":coupon is not None and not issues,"issues":issues,"stale":stale,"enabled":self.config.enabled,
            "message":f"Live-data kunde inte uppdateras. Visar senast sparad data från {iso(selected.retrieved_at)}." if stale else None,
            "health":health,"next_refresh_at":iso(selected.retrieved_at+timedelta(seconds=interval)),
            "manual_odds_matches":sum(item['market']['provider']=='manual' for item in inputs.values()),
            "market_status":self.market.health(),
            "market_sources":{str(n):inputs[str(n)]['market']['market_source'] if str(n) in inputs else 'unavailable' for n in range(1,14)},
            "available_draws":[{"draw_number":d.draw_number,"sales_close_at":iso(d.sales_close_at),"status":d.status} for d in self.repo.draws() if d.sales_close_at>at and d.status in ('open','upcoming')],
            "mapping":self.mapping(selected),"movement":self.movement(selected.draw_number,at)}

    @staticmethod
    def mapping(draw: Draw) -> dict:
        unmapped = sorted({name for m in draw.matches for name,identifier in ((m.source_home_team,m.home_team_id),(m.source_away_team,m.away_team_id)) if identifier is None})
        return {"references":26,"mapped":sum(bool(i) for m in draw.matches for i in (m.home_team_id,m.away_team_id)),"unmapped":unmapped,"supported_model_matches":sum(m.model_coverage for m in draw.matches)}

    def coupon_at(self, draw_number: int, at: datetime) -> tuple[Coupon | None,list[str],dict]:
        observation = self.repo.observation_asof(draw_number,at)
        if not observation:
            return None,["Ingen kupongobservation fanns vid denna tidpunkt."],{}
        draw = Draw.model_validate(observation['draw'])
        crowd, market = self.repo.inputs_asof(draw_number,at)
        consensus = self.market.candidates(draw_number,at)
        import json
        with self.repo.connection() as con:
            source_market={r[0]:json.loads(r[1]) for r in con.execute('SELECT number,payload FROM market_snapshots WHERE observation_id=? AND recorded_at<=? AND retrieved_at<=?',(observation['id'],iso(at),iso(at)))}
        issues = list(draw.issues)
        if at >= draw.sales_close_at or draw.status != 'open':
            issues.append("Omgången är inte öppen. Historiska prognoser skapas inte i efterhand.")
        if draw.row_price is not None and abs(draw.row_price-ROW_COST)>1e-9:
            issues.append("Leverantörens radpris skiljer sig från optimizerkonfigurationen.")
        matches, inputs = [], {}
        for m in draw.matches:
            q,p = crowd.get(m.number),source_market.get(m.number) or market.get(m.number)
            if q and (not m.crowd or q['observation_id'] != observation['id'] or q.get('fixture_key') != fixture_key(m)):
                q = None
            if p and (p.get('fixture_key') != fixture_key(m) or (p['provider'] != 'manual' and (p['observation_id'] != observation['id'] or not m.market_odds))):
                p = None
            p = self.market.select(m,consensus.get(m.number),p,at)
            if not q:
                issues.append(f"Match {m.number}: giltiga observerade folkstreck saknas vid analystidpunkten.")
            if not p:
                issues.append(f"Match {m.number}: marknadsodds saknas. Ange odds manuellt.")
            if not m.kickoff_at or m.kickoff_at <= at or m.cancelled or m.status not in ('NotStarted',None):
                issues.append(f"Match {m.number}: kickoff saknas eller matchen har startat/ställts in.")
            if not q or not p or not m.kickoff_at:
                continue
            matches.append(CouponMatch(number=m.number,homeTeam=m.home_team,awayTeam=m.away_team,date=m.kickoff_at.astimezone(STOCKHOLM).date(),
                league=m.league or 'UNSUPPORTED',competition=m.competition,modelCoverage=m.model_coverage,
                marketOdds=Odds(**p['odds']),crowd=Crowd(**{k:v*100 for k,v in q['crowd'].items()}),
                oddsSnapshot=Snapshot(source=p['source'],recorded_at=p['recorded_at'],retrieved_at=p['retrieved_at'],source_updated_at=p['source_updated_at']),
                crowdSnapshot=Snapshot(source=q['source'],recorded_at=q['recorded_at'],retrieved_at=q['retrieved_at'],source_updated_at=q['source_updated_at']),
                kickoffAt=m.kickoff_at,providerEventId=m.provider_event_id,crowdMatchId=m.match_id))
            matches[-1].marketSource = p['market_source']
            matches[-1].marketQuality = {k:p.get(k) for k in ('bookmaker_count','confidence','dispersion','oldest_bookmaker_update','newest_bookmaker_update','raw_reference')}
            inputs[str(m.number)] = {"draw_observation_id":observation['id'],"crowd":q,"market":p}
        coupon = Coupon(id=f"stryktipset-{draw_number}",week=draw.draw_date.isocalendar().week,date=draw.draw_date,demo=False,
            drawNumber=draw_number,salesCloseAt=draw.sales_close_at,retrievedAt=draw.retrieved_at,dataSource='svenska-spel',drawStatus=draw.status,matches=matches) if len(matches)==13 else None
        return coupon,issues,inputs

    def analyze_live(self, draw_number: int | None, budget=256, mode='optimal', at: datetime | None = None) -> dict:
        if draw_number is None:
            current = self.current()
            if not current['draw']:
                raise DrawNotReady(current['message'])
            draw_number = current['draw']['draw_number']
        at = at or now_utc()
        coupon,issues,inputs = self.coupon_at(draw_number,at)
        if not coupon or issues:
            raise DrawNotReady(" ".join(issues))
        # The prediction artifact itself must also have existed at the cutoff.
        self.predictor.load()
        metadata = self.predictor.bundle['metadata'] if self.predictor.bundle else {}
        if metadata.get('trained_at') and datetime.fromisoformat(metadata['trained_at']) > at:
            raise DrawNotReady("Modellartefakten är nyare än analystidpunkten.")
        import os
        artifact_hash=hashlib.sha256(self.predictor.path.read_bytes()).hexdigest() if self.predictor.path.exists() else None
        if os.getenv('ENVIRONMENT')=='production':
            previous=self.repo.latest_system(draw_number,at,budget,mode)
            if previous and previous['inputs']==inputs and previous['model'].get('artifact_sha256')==artifact_hash and previous['model'].get('active_model')==metadata.get('activeModel'):
                return {**previous['analysis'],'snapshotId':previous['id'],'changes':previous['changes'],'reusedSnapshot':True}
        result = analyze(AnalyzeRequest(coupon=coupon,budget=budget,mode=mode),self.predictor)
        result['analyzedAt'] = iso(at)
        result['drawNumber'] = draw_number
        result['inputCoupon'] = coupon.model_dump(mode='json')
        result['drawSnapshot'] = self.repo.observation_asof(draw_number,at)['draw']
        result['movement'] = self.movement(draw_number,at)
        model = {"version":metadata.get('modelVersion'),"active_model":metadata.get('activeModel'),"trained_at":metadata.get('trained_at'),
                 "optimizer_version":"objective-v1",
                 "artifact_sha256":artifact_hash,
                 "news_affects_probabilities":False,"crowd_movement_affects_probabilities":False}
        saved = self.repo.save_analysis(self.repo.draw(draw_number),result,inputs,at,model)
        result['snapshotId'],result['changes'] = saved['id'],saved['changes']
        return result

    def movement(self, draw_number: int, at: datetime) -> list[dict]:
        import json
        histories={n:[] for n in range(1,14)}
        with self.repo.connection() as con:
            for row in con.execute('SELECT number,payload FROM crowd_snapshots WHERE draw_number=? AND recorded_at<=? AND retrieved_at<=? AND (source_updated_at IS NULL OR source_updated_at<=?) ORDER BY retrieved_at,recorded_at,id',(draw_number,iso(at),iso(at),iso(at))):
                histories[row[0]].append(json.loads(row[1]))
        return [{'number':n,**movements(history)} for n,history in histories.items()]

    def update_results(self, draw_number: int, force=False) -> dict:
        draw=self.repo.draw(draw_number)
        if not draw:
            self.ingest(draw_number)
            draw=self.repo.draw(draw_number)
        if not draw:
            raise DrawNotReady("Omgången saknas och kunde inte hämtas.")
        if draw.sales_close_at>now_utc():
            raise DrawNotReady("Resultat hämtas efter spelstopp.")
        existing=self.repo.result(draw_number)
        if existing and existing['completed'] and not force:
            return existing
        result=self.provider.get_results(draw_number,refresh=force or bool(existing and not existing['completed']))
        expected={m.number:m.provider_event_id for m in draw.matches}
        if any(m.provider_event_id and expected[m.number] and m.provider_event_id!=expected[m.number] for m in result.matches):
            raise ProviderSchemaError("Result event identities do not match archived draw")
        self.repo.save_result(result,now_utc())
        if result.completed:
            import json
            completed_draw = draw.model_copy(update={'status':'completed'})
            with self.repo.connection() as con:
                con.execute("UPDATE stryktipset_draws SET status='completed',payload=? WHERE draw_number=?",(json.dumps(completed_draw.model_dump(mode='json')),draw_number))
        return self.repo.result(draw_number)

    def archive(self) -> list[dict]:
        at=now_utc()
        rows=[]
        for draw in self.repo.draws():
            result=self.repo.result(draw.draw_number)
            system=self.repo.latest_system(draw.draw_number,min(at,draw.sales_close_at))
            rows.append({"draw_number":draw.draw_number,"draw_date":str(draw.draw_date),"sales_close_at":iso(draw.sales_close_at),
                "status":"completed" if result and result['completed'] else 'closed' if at>=draw.sales_close_at else draw.status,
                "matches":len(draw.matches),"crowd_data_available":all(m.crowd for m in draw.matches),
                "pre_close_available":self.repo.pre_close(draw.draw_number) is not None,
                "result_available":bool(result and result['completed']),"payout_available":bool(result and result['payouts']),
                "system":self.system_summary(system,result),"snapshots":len(self.repo.observations(draw.draw_number))})
        return rows

    @staticmethod
    def system_summary(system, result):
        if not system:
            return None
        scores={m['number']:m['outcome'] for m in result['matches']} if result and result['completed'] else {}
        selections=system['analysis']['system']['selections']
        return {"id":system['id'],"created_at":system['created_at'],"model":system['model'],"system":system['analysis']['system'],
                "max_covered_correct":sum(scores.get(i+1) in s for i,s in enumerate(selections)) if scores else None,
                "is_submitted":False}

    def history(self, draw_number: int, selection='pre_close', at: datetime | None = None) -> dict:
        draw=self.repo.draw(draw_number)
        if not draw:
            raise DrawNotReady("Omgången saknas i arkivet.")
        observations=self.repo.observations(draw_number)
        cutoff=at
        if cutoff is None:
            if selection=='first':
                cutoff=datetime.fromisoformat(observations[0]['recorded_at']) if observations else now_utc()
            elif selection=='24h':
                cutoff=draw.sales_close_at-timedelta(hours=24)
            elif selection=='latest':
                cutoff=now_utc()
            else:
                cutoff=min(now_utc(),draw.sales_close_at-timedelta(microseconds=1))
        observation=self.repo.observation_asof(draw_number,cutoff)
        crowd,market=self.repo.inputs_asof(draw_number,cutoff)
        pre_close=self.repo.pre_close(draw_number)
        if selection=='pre_close' and at is None:
            # A later incomplete retrieval must not combine unrelated crowd batches.
            observation=next((o for o in observations if pre_close and o['id']==pre_close['observation_id'] and datetime.fromisoformat(o['recorded_at'])<=cutoff),None)
            if observation:
                crowd,_=self.repo.inputs_asof(draw_number,datetime.fromisoformat(observation['recorded_at']))
                crowd={n:q for n,q in crowd.items() if q['observation_id']==observation['id']}
            else:
                crowd={}
        system=self.repo.latest_system(draw_number,cutoff)
        result=self.repo.result(draw_number)
        return {"draw":draw.model_dump(mode='json'),"as_of":iso(cutoff),"selection":selection,
                "observation":{k:v for k,v in observation.items() if k!='payload'} if observation else None,
                "crowd":crowd,"market":market,"optimizer":system,"system_summary":self.system_summary(system,result),
                "result":result,"result_is_post_match":True,"pre_close":pre_close,
                "snapshots":[{"id":o['id'],"recorded_at":o['recorded_at'],"retrieved_at":o['retrieved_at']} for o in observations],
                "message":None if observation else "Inga observationer registrerades före denna tidpunkt. Historisk slutdata kan visas separat; den bakdateras inte."}
