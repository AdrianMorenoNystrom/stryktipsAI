from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import httpx
import pytest
from fastapi.testclient import TestClient
from app.schemas import Odds
from app.stryktipset.config import DrawConfig, BASE_URL
from app.stryktipset.parser import ProviderSchemaError, draw_objects, parse_draw, parse_result
from app.stryktipset.provider import SvenskaSpelProvider, ProviderUnavailable
from app.stryktipset.repository import DrawRepository
from app.stryktipset.service import DrawService, DrawNotReady, choose_current, movements
from app.stryktipset.teams import map_team

FIXTURES=Path(__file__).parent/'fixtures'/'stryktipset'
AT=datetime(2026,9,9,20,30,tzinfo=timezone.utc)


def fixture(name='current.json'):
    return json.loads((FIXTURES/name).read_bytes())


def parsed(raw=None, at=AT, identifier='raw'):
    return parse_draw(raw or fixture()['draws'][0],at,BASE_URL+'/draws',identifier)


@pytest.fixture
def live(tmp_path,monkeypatch):
    clock=[AT]
    for module in ('app.stryktipset.service','app.stryktipset.provider','app.stryktipset.api'):
        monkeypatch.setattr(module+'.now_utc',lambda:clock[0])
    config=DrawConfig(root=tmp_path/'live',enabled=True,request_interval=0)
    repo=DrawRepository(config.root)
    payload=fixture()
    calls=[]
    def handle(request):
        calls.append(request)
        return httpx.Response(200,json=payload)
    provider=SvenskaSpelProvider(config,repo,httpx.Client(transport=httpx.MockTransport(handle)))
    return DrawService(config,provider),clock,payload,calls


def test_observed_current_and_specific_draw_mapping_and_odds_separation():
    draw=parsed()
    assert draw.draw_number==4970 and len(draw.matches)==13 and draw.status=='open'
    assert draw.sales_close_at.isoformat()=='2026-09-12T13:59:00+00:00'
    first=draw.matches[0]
    assert first.home_team=='Sunderland' and first.away_team=='Arsenal'
    assert first.crowd.home==.24 and first.market_odds.home==7.5
    assert first.crowd_source_updated_at<draw.retrieved_at
    assert DrawService.mapping(draw)=={'references':26,'mapped':26,'unmapped':[],'supported_model_matches':13}
    assert draw.matches[5].away_team=='Nottingham Forest'
    assert map_team('Man Utd')==map_team('Manchester United')
    assert map_team('Unknown Example Club')[1] is None
    assert parse_draw(draw_objects(fixture('specific.json'),True)[0],AT,'source','specific').draw_number==4970


def test_current_selection_never_uses_response_order():
    draw=parsed()
    later=draw.model_copy(update={'draw_number':6000,'sales_close_at':draw.sales_close_at+timedelta(days=7)})
    closed=draw.model_copy(update={'draw_number':4000,'status':'completed','sales_close_at':AT-timedelta(days=1)})
    assert choose_current([later,closed,draw],AT).draw_number==4970
    assert choose_current([draw,later],AT).draw_number==4970
    assert choose_current([closed],AT) is None
    assert choose_current([draw],draw.sales_close_at) is None


@pytest.mark.parametrize('change',[
    lambda r:r['drawEvents'].pop(),
    lambda r:r['drawEvents'].append(deepcopy(r['drawEvents'][0])),
    lambda r:r['drawEvents'][0].update(eventNumber=2),
    lambda r:r['drawEvents'][0]['match']['participants'].pop(),
    lambda r:r['drawEvents'][0]['match']['participants'][0].update(name=''),
    lambda r:r.pop('drawEvents'),
    lambda r:r.update(drawState='NewUnexpectedState'),
    lambda r:r.update(productName='Europatipset'),
    lambda r:r.update(regCloseTime=None),
])
def test_schema_drift_and_incomplete_coupons_fail_clearly(change):
    raw=fixture()['draws'][0];change(raw)
    with pytest.raises(ProviderSchemaError): parsed(raw)


@pytest.mark.parametrize('crowd',[None,{'one':'70','x':'70','two':'20'},{'one':'24','x':None,'two':'76'},{'one':'NaN','x':'0','two':'0'}])
def test_missing_or_invalid_crowd_stays_unavailable(crowd):
    raw=fixture()['draws'][0];raw['drawEvents'][0]['svenskaFolket']=crowd
    draw=parsed(raw)
    assert draw.matches[0].crowd is None and draw.matches[0].issues
    assert draw.matches[0].market_odds.home==7.5


def test_rounding_and_missing_odds_never_use_crowd_or_start_odds():
    raw=fixture()['draws'][0];e=raw['drawEvents'][0]
    e['svenskaFolket']={'one':'33','x':'33','two':'33'};e['odds']=None
    draw=parsed(raw)
    assert draw.matches[0].crowd.home==pytest.approx(1/3)
    assert draw.matches[0].market_odds is None


def test_legacy_crowd_unknown_timestamp_and_real_payout():
    draw=parse_draw(fixture('legacy.json')['draw'],AT,'legacy','raw')
    assert draw.draw_number==4267 and str(draw.draw_date)=='2013-01-12'
    assert all(m.crowd is not None and m.crowd_source_updated_at is None for m in draw.matches)
    result=parse_result(fixture('legacy_result.json'),AT,'result','raw-result',4267)
    assert result.completed and result.payouts[0].amount==5250000


def test_observed_results_goals_and_payout_nulls():
    payload=fixture('result.json')
    result=parse_result(payload,AT,'source','raw',4969)
    assert result.completed and len(result.matches)==13
    assert {m.outcome for m in result.matches}=={'1','X','2'}
    assert result.matches[0].home_goals==result.matches[0].away_goals==0
    assert [(p.correct,p.amount) for p in result.payouts]==[(13,764705),(12,6227),(11,383),(10,98)]
    payload['result']['distribution'][0]['amount']=None
    assert parse_result(payload,AT,'s','r',4969).payouts[0].amount is None
    payload['result']['events'][0]['outcome']='1'
    with pytest.raises(ProviderSchemaError):parse_result(payload,AT,'s','r',4969)


def test_ingestion_idempotency_cache_and_immutable_raw(live):
    service,clock,payload,calls=live
    service.ingest(force=True)
    first=service.repo.counts()
    service.ingest()
    assert len(calls)==1 and service.repo.counts()==first
    clock[0]+=timedelta(minutes=1)
    service.ingest(force=True)
    counts=service.repo.counts()
    assert counts['stryktipset_draws']==1 and counts['stryktipset_matches']==13
    assert counts['crowd_snapshots']==26 and counts['draw_observations']==2
    assert counts['provider_raw_payloads']==2
    assert len(list((service.repo.root/'raw').glob('*.raw')))==1


def test_movement_and_probability_isolation_and_optimizer_snapshots(live):
    service,clock,payload,calls=live
    service.ingest(force=True)
    before=service.analyze_live(4970,256,'optimal')
    clock[0]+=timedelta(minutes=2)
    q=payload['draws'][0]['drawEvents'][0]['svenskaFolket'];q.update(one='28',x='17',two='55')
    service.ingest(force=True)
    after=service.analyze_live(4970,256,'optimal')
    assert [m['model'] for m in before['matches']]==[m['model'] for m in after['matches']]
    assert before['matches'][0]['crowd']!=after['matches'][0]['crowd']
    history=service.repo.crowd_history(4970,1,clock[0])
    assert movements(history)['since_first']==pytest.approx({'home':.04,'draw':-.02,'away':-.02})
    assert history[0]['crowd']['home']==.24
    counts=service.repo.counts()
    assert counts['prediction_snapshots']==26 and counts['optimizer_snapshots']==2
    assert before['snapshotId']!=after['snapshotId']
    latest=service.repo.latest_system(4970,clock[0])
    assert latest['inputs']['1']['crowd']['recorded_at']<=latest['created_at']
    assert latest['model']['news_affects_probabilities'] is False


def test_pre_close_selection_and_asof_exclude_future_observations(tmp_path):
    repo=DrawRepository(tmp_path)
    close=datetime(2026,9,12,16,tzinfo=timezone.utc)
    base=parsed().model_copy(update={'sales_close_at':close})
    for hour,minute in [(15,0),(15,30),(15,55),(16,5)]:
        at=close.replace(hour=hour,minute=minute)
        draw=base.model_copy(deep=True,update={'retrieved_at':at,'raw_id':str(at)})
        for m in draw.matches:m.crowd_source_updated_at=at
        repo.save_draw(draw,at)
    cutoff=close.replace(hour=15,minute=30)
    first=repo.crowd_history(4970,1,cutoff)
    assert len(first)==2
    assert repo.pre_close(4970)['at'].startswith('2026-09-12T15:55:00')
    assert len(repo.crowd_history(4970,1,close+timedelta(hours=1)))==4
    assert repo.inputs_asof(4970,cutoff)[0][1]['recorded_at'].startswith('2026-09-12T15:30:00')


def test_historical_fetch_never_creates_preclose_data(live):
    service,clock,payload,calls=live
    old=parse_draw(fixture('historical.json')['draw'],AT,'source','historical')
    service.repo.save_draw(old,AT)
    assert service.repo.pre_close(4969) is None
    assert service.history(4969)['observation'] is None
    assert service.history(4969,'latest',AT)['observation'] is not None
    with pytest.raises(DrawNotReady):service.analyze_live(4969,at=AT)


def test_missing_odds_manual_completion_and_uncovered_league(live,monkeypatch):
    # Exercise the portable production policy even on a clean checkout without ML artifacts.
    monkeypatch.setenv('ENVIRONMENT','production')
    service,clock,payload,calls=live
    raw=payload['draws'][0]['drawEvents'][0]
    raw['odds']=None
    raw['match']['league']={'name':'Allsvenskan','country':{'isoCode':'SWE'}}
    service.ingest(force=True)
    assert not service.current()['analysis_ready']
    with pytest.raises(DrawNotReady):service.analyze_live(4970)
    service.repo.save_manual_odds(service.repo.draw(4970),{1:Odds(home=7.5,draw=4.4,away=1.5).model_dump()},clock[0])
    result=service.analyze_live(4970)
    assert result['matches'][0]['source']=='market_fallback'
    assert result['matches'][0]['oddsSnapshot']['source']=='manual'
    assert 'No trained league coverage' in result['matches'][0]['warnings'][0]


def test_replaced_match_or_invalid_latest_crowd_cannot_reuse_old_inputs(live):
    service,clock,payload,calls=live
    service.ingest(force=True)
    clock[0]+=timedelta(minutes=2)
    payload['draws'][0]['drawEvents'][0]['svenskaFolket']=None
    service.ingest(force=True)
    with pytest.raises(DrawNotReady):service.analyze_live(4970)
    raw=payload['draws'][0]['drawEvents'][0]
    raw['svenskaFolket']=fixture()['draws'][0]['drawEvents'][0]['svenskaFolket']
    service.repo.save_manual_odds(service.repo.draw(4970),{1:{'home':2,'draw':3,'away':4}},clock[0])
    raw['odds']=None;raw['match']['matchId']=999999
    clock[0]+=timedelta(minutes=2);service.ingest(force=True)
    with pytest.raises(DrawNotReady):service.analyze_live(4970)


def test_provider_failure_and_schema_error_preserve_saved_state(live):
    service,clock,payload,calls=live
    service.ingest(force=True)
    before=service.repo.counts()
    clock[0]+=timedelta(hours=7)
    payload.clear();payload['schema_changed']=True
    state=service.current(refresh=True)
    assert state['stale'] and state['draw']['draw_number']==4970
    assert state['health']['status']=='Degraded' and 'schema' in state['health']['issue']
    assert service.repo.counts()['crowd_snapshots']==before['crowd_snapshots']
    assert service.repo.counts()['provider_raw_payloads']==before['provider_raw_payloads']+1


def test_api_live_flow_uses_server_observations_and_snapshots(live,monkeypatch):
    from app.main import app
    service,clock,payload,calls=live
    monkeypatch.setattr('app.stryktipset.api.DrawService',lambda:service)
    monkeypatch.setattr('app.main.DrawService',lambda **_:service)
    client=TestClient(app)
    state=client.get('/api/coupon/current').json()
    assert state['analysis_ready'] and not state['coupon']['demo']
    for budget in (64,128,256,512):
        result=client.post('/api/coupon/current/analyze',json={'drawNumber':4970,'budget':budget,'mode':'optimal'})
        assert result.status_code==200,result.text
        assert result.json()['system']['cost']<=budget
    # Client-mutated live crowd must not impersonate observed provider data.
    coupon=deepcopy(state['coupon']);coupon['matches'][0]['crowd']={'home':90,'draw':5,'away':5}
    analyzed=client.post('/api/coupon/analyze',json={'coupon':coupon}).json()
    assert analyzed['matches'][0]['crowd']['home']==.24
    assert client.get('/api/stryktipset/draws').json()[0]['system']
    assert len(client.get('/api/stryktipset/draws/4970/matches/1/crowd').json()['history'])==1
    assert client.post('/api/coupon/current/refresh',headers={'Origin':'https://untrusted.example'}).status_code==403
    assert client.get('/api/stryktipset/draws/4970?as_of=2099-01-01T12:00:00Z').status_code==422
    assert len(calls)==1


def test_source_time_in_future_is_not_a_prediction_input(live):
    service,clock,payload,calls=live
    payload['draws'][0]['drawEvents'][0]['svenskaFolket']['date']=(AT+timedelta(minutes=10)).isoformat()
    service.ingest(force=True)
    with pytest.raises(DrawNotReady):service.analyze_live(4970)


def test_snapshot_policy_is_scheduler_independent():
    config=DrawConfig()
    close=datetime(2026,9,12,14,tzinfo=timezone.utc)
    assert config.interval(close-timedelta(hours=1),close)==1800
    assert config.interval(close-timedelta(hours=5),close)==1800
    assert config.interval(close-timedelta(hours=12),close)==3600
    assert config.interval(close-timedelta(hours=30),close)==7200
    assert config.interval(close-timedelta(days=3),close)==21600
    assert config.interval(close-timedelta(minutes=2),close)==300


def test_empty_provider_response_and_failures_are_rate_limited(live):
    service,clock,payload,calls=live
    payload['draws']=[]
    assert service.current()['draw'] is None
    assert service.current(refresh=True)['draw'] is None
    assert len(calls)==1
    clock[0]+=timedelta(minutes=2)
    payload.clear()
    service.current(refresh=True)
    service.current(refresh=True)
    assert len(calls)==2


def test_old_reparse_cannot_replace_newer_known_inputs(live):
    service,clock,payload,calls=live
    service.ingest(force=True)
    original=service.repo.draw(4970)
    clock[0]+=timedelta(minutes=3)
    payload['draws'][0]['drawEvents'][0]['svenskaFolket']['one']='28'
    payload['draws'][0]['drawEvents'][0]['svenskaFolket']['two']='53'
    service.ingest(force=True)
    clock[0]+=timedelta(minutes=1)
    old=original.model_copy(update={'raw_id':'reparse-old'})
    service.repo.save_draw(old,clock[0])
    assert service.repo.inputs_asof(4970,clock[0])[0][1]['crowd']['home']==.28
    assert service.repo.observation_asof(4970,clock[0])['draw']['matches'][0]['crowd']['home']==.28
    assert service.movement(4970,clock[0])[0]['since_previous']['home']==pytest.approx(.04)
    assert service.repo.pre_close(4970)['at'] < clock[0].isoformat()


def test_alias_cannot_redirect_an_existing_canonical_team():
    from app.stryktipset.teams import save_alias
    with pytest.raises(ValueError):save_alias('Arsenal','Everton')


def test_http_retry_archives_each_response_and_connection_failure_keeps_cache(live,monkeypatch):
    service,clock,payload,calls=live
    monkeypatch.setattr('app.stryktipset.provider.time.sleep',lambda _:None)
    statuses=iter([429,503,200])
    def handle(request):
        calls.append(request)
        status=next(statuses)
        return httpx.Response(status,json=payload if status==200 else {'error':status})
    service.provider.client=httpx.Client(transport=httpx.MockTransport(handle))
    service.ingest(force=True)
    assert service.repo.counts()['provider_raw_payloads']==3
    assert len(calls)==3
    def unavailable(request):
        raise httpx.ConnectError('offline',request=request)
    service.provider.client=httpx.Client(transport=httpx.MockTransport(unavailable))
    clock[0]+=timedelta(hours=7)
    state=service.current(refresh=True)
    assert state['stale'] and state['health']['status']=='Degraded'
    assert state['draw']['draw_number']==4970
    assert service.repo.counts()['crowd_snapshots']==13


def test_pre_close_history_selects_complete_batch_and_partial_results_refresh(live,monkeypatch):
    service,clock,payload,calls=live
    service.ingest(force=True)
    first=service.repo.observations(4970)[0]['id']
    clock[0]+=timedelta(minutes=2)
    payload['draws'][0]['drawEvents'][0]['svenskaFolket']=None
    service.ingest(force=True)
    history=service.history(4970)
    assert len(history['crowd'])==13
    assert {q['observation_id'] for q in history['crowd'].values()}=={first}
    assert history['observation']['id']==first
    draw=parse_draw(draw_objects(fixture('historical.json'),True)[0],clock[0],'history','history')
    service.repo.save_draw(draw,clock[0])
    result=parse_result(fixture('result.json'),clock[0],'results','r1',4969)
    service.repo.save_result(result.model_copy(update={'completed':False}),clock[0])
    refreshed=[]
    def get_results(n,refresh=False):
        refreshed.append(refresh)
        return result.model_copy(update={'raw_id':'r2'})
    monkeypatch.setattr(service.provider,'get_results',get_results)
    clock[0]+=timedelta(seconds=1)
    assert service.update_results(4969)['completed']
    assert refreshed==[True]


def test_disabled_provider_cannot_fetch_results_or_an_unknown_draw(live):
    service,clock,payload,calls=live
    service.config.enabled=False
    with pytest.raises(ProviderUnavailable):service.provider.get_results(4969,refresh=True)
    with pytest.raises(DrawNotReady):service.update_results(4969)
    assert calls==[]
