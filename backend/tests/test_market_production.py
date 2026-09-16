"""Provider fixtures below are explicit test data, never labelled as observed live odds."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
from uuid import uuid4
import httpx
import pytest
from app.market.config import MarketConfig
from app.market.consensus import consensus, match_event
from app.market.provider import TheOddsApiProvider, OddsUnavailable
from app.market.service import MarketService
from app.stryktipset.repository import DrawRepository
from app.stryktipset.config import DrawConfig
from app.stryktipset.parser import parse_draw
from app.stryktipset.service import DrawService
from app.stryktipset.provider import SvenskaSpelProvider
from app.services.probabilities import devig
from app.collection import collect
from app.runtime import Runtime

AT=datetime(2026,9,9,21,tzinfo=timezone.utc)
FIXTURE=Path(__file__).parent/'fixtures/stryktipset/current.json'


def raw_coupon():
    return json.loads(FIXTURE.read_bytes())


def odds_event(match):
    from app.market.config import SPORT_KEYS
    return {'id':'test-event-'+str(match.number),'sport_key':SPORT_KEYS[match.league],
        'home_team':match.home_team,'away_team':match.away_team,'commence_time':match.kickoff_at.isoformat(),
        'bookmakers':[{'key':'test-book-'+str(i),'title':'Test bookmaker','last_update':(AT-timedelta(minutes=i)).isoformat(),
            'markets':[{'key':'h2h','outcomes':[{'name':match.away_team,'price':4+i*.1},{'name':'Draw','price':3.2+i*.1},{'name':match.home_team,'price':2+i*.1}]}]} for i in range(3)]}


def draw():
    return parse_draw(raw_coupon()['draws'][0],AT,'test-provider','test-raw')


@pytest.fixture
def service(tmp_path,monkeypatch):
    for module in ('app.collection','app.stryktipset.service','app.stryktipset.provider','app.market.service','app.market.provider'):
        monkeypatch.setattr(module+'.now_utc',lambda:AT)
    config=DrawConfig(root=tmp_path/'archive',enabled=True,request_interval=0)
    repo=DrawRepository(config.root)
    provider=SvenskaSpelProvider(config,repo,httpx.Client(transport=httpx.MockTransport(lambda _:httpx.Response(200,json=raw_coupon()))))
    return DrawService(config,provider)


def test_consensus_definitions_and_quality():
    event=odds_event(draw().matches[0])
    result=consensus(event,AT,MarketConfig())
    assert result['bookmaker_count']==3 and result['eligible']
    assert result['average_odds']==pytest.approx({'home':2.1,'draw':3.3,'away':4.1})
    assert result['consensus']==devig(result['average_odds'])
    assert sum(result['median'].values())==pytest.approx(1)
    assert all(sum(b['probabilities'].values())==pytest.approx(1) for b in result['bookmakers'])
    assert result['dispersion']['home']>0
    event['bookmakers'][0]['last_update']=(AT+timedelta(minutes=1)).isoformat()
    assert consensus(event,AT,MarketConfig())['bookmaker_count']==2
    assert not consensus(event,AT,MarketConfig())['eligible']


def test_event_matching_rejects_wrong_teams_league_time_and_ambiguity():
    match=draw().matches[0];event=odds_event(match);config=MarketConfig()
    assert match_event(match,[event],config)==event
    assert match_event(match,[event,event],config) is None
    for key,value in [('sport_key','soccer_efl_champ'),('away_team','Chelsea'),('commence_time',AT.isoformat())]:
        invalid=deepcopy(event);invalid[key]=value
        assert match_event(match,[invalid],config) is None


def test_malformed_bookmakers_are_rejected_without_losing_other_coverage():
    event=odds_event(draw().matches[0])
    event['bookmakers'] += [None, {'key':'bad','markets':[None]}, {'key':'other','markets':None}]
    assert consensus(event,AT,MarketConfig())['bookmaker_count']==3
    event['home_team']=None
    assert match_event(draw().matches[0],[event],MarketConfig()) is None


def test_provider_key_redaction_cache_and_quota(service,caplog):
    key='unit-test-not-a-real-api-key'
    event=odds_event(draw().matches[0]);calls=[]
    def handle(request):
        calls.append(request)
        return httpx.Response(200,json=[event],headers={'x-requests-remaining':'42','x-requests-used':'1'})
    provider=TheOddsApiProvider(service.repo,MarketConfig(api_key=key),httpx.Client(transport=httpx.MockTransport(handle)))
    first,meta=provider.get_upcoming_events('E0')
    assert provider.get_upcoming_events('E0')[0]==first and len(calls)==1
    assert meta['quota']['x-requests-remaining']=='42'
    assert key not in json.dumps(meta) and key not in caplog.text
    with service.repo.connection() as con:
        assert key not in con.execute('SELECT payload FROM odds_requests').fetchone()[0]


def test_full_collection_consensus_snapshot_ids_and_partial_failure(service):
    events=[odds_event(m) for m in draw().matches]
    config=MarketConfig(api_key='unit-test')
    client=httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(200,json=[e for e in events if e['sport_key'] in r.url.path])))
    service.market=MarketService(service.repo,config,TheOddsApiProvider(service.repo,config,client))
    result=collect(service,force=True)
    assert result['status']=='completed',result
    assert result['prediction_status']['saved']==13
    assert len(result['market_status']['matched'])==13
    saved=service.repo.latest_system(4970,AT)
    assert all(i['market']['market_source']=='bookmaker_consensus' for i in saved['inputs'].values())
    assert all(m['model']==m['market'] for m in saved['analysis']['matches'])
    assert len({i['market']['id'] for i in saved['inputs'].values()})==13
    with service.repo.connection() as con:
        assert con.execute('SELECT COUNT(*) FROM odds_requests').fetchone()[0]==2
        assert con.execute('SELECT COUNT(*) FROM bookmaker_observations').fetchone()[0]==39
    assert collect(service)['crowd_status']=='not_due'
    service.market=MarketService(service.repo,MarketConfig())
    partial=collect(service,force=True)
    assert partial['status']=='partial' and partial['prediction_status']['saved']==13


def test_fallback_age_future_and_fixture_safety(service):
    service.ingest(force=True)
    m=service.repo.draw(4970).matches[0];event=odds_event(m)
    service.market.save(draw(),m,event,{'id':'request','retrieved_at':AT.isoformat(),'raw_reference':'test'},consensus(event,AT,MarketConfig()))
    q,issues,inputs=service.coupon_at(4970,AT)
    assert inputs['1']['market']['market_source']=='bookmaker_consensus'
    assert service.coupon_at(4970,AT+timedelta(hours=1))[2]['1']['market']['market_source']=='cached_consensus'
    assert service.coupon_at(4970,AT+timedelta(hours=7))[2]['1']['market']['market_source']=='svenska_spel_odds'
    assert service.market.candidates(4970,AT-timedelta(seconds=1))=={}
    candidate=service.market.candidates(4970,AT)[1]
    assert service.market.select(m.model_copy(update={'provider_event_id':'other'}),candidate,None,AT) is None


def test_production_configuration_and_portable_market_policy(tmp_path,monkeypatch):
    monkeypatch.setenv('ENVIRONMENT','production')
    with pytest.raises(ValueError):Runtime.load()
    monkeypatch.setenv('DATABASE_URL','postgresql://localhost/test')
    monkeypatch.setenv('ALLOWED_ORIGINS','*')
    with pytest.raises(ValueError):Runtime.load()
    monkeypatch.setenv('ALLOWED_ORIGINS','https://example.github.io')
    assert Runtime.load().production
    from ml.predict import PredictionService
    from app.schemas import MatchInput,Odds
    prediction=PredictionService(tmp_path).predict(MatchInput(homeTeam='Arsenal',awayTeam='Chelsea',league='E0',date='2026-09-12',marketOdds=Odds(home=2,draw=3,away=4)))
    assert prediction['source']=='market_baseline' and prediction['model']==prediction['market']


def test_invalid_success_response_is_not_healthy_or_retried_immediately(service):
    calls=[]
    def invalid(request):
        calls.append(request)
        return httpx.Response(200, content=b'{invalid json')
    config=MarketConfig(api_key='unit-test')
    service.market=MarketService(service.repo,config,TheOddsApiProvider(service.repo,config,httpx.Client(transport=httpx.MockTransport(invalid))))
    for _ in range(2):
        with pytest.raises(OddsUnavailable):
            service.market.provider.get_upcoming_events('E0')
    assert len(calls)==1
    assert service.market.health()['status']=='Unavailable'
    assert service.market.health()['last_successful_fetch'] is None


def test_production_reuses_exact_inputs_and_records_changed_budget(service,monkeypatch):
    service.ingest(force=True)
    monkeypatch.setenv('ENVIRONMENT','production')
    first=service.analyze_live(4970)
    second=service.analyze_live(4970)
    assert first['snapshotId']==second['snapshotId'] and second['reusedSnapshot']
    assert service.repo.counts()['prediction_snapshots']==13
    changed=service.analyze_live(4970,budget=512)
    assert changed['snapshotId']!=first['snapshotId']
    assert service.repo.counts()['optimizer_snapshots']==2


@pytest.fixture
def postgres(tmp_path,monkeypatch):
    url=os.getenv('TEST_DATABASE_URL')
    if not url:
        pytest.skip('TEST_DATABASE_URL not configured; CI supplies an isolated Postgres service')
    import psycopg
    from psycopg import sql
    from urllib.parse import urlencode
    schema='v4_test_'+uuid4().hex
    with psycopg.connect(url,autocommit=True) as con:
        con.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
    scoped=url+('&' if '?' in url else '?')+urlencode({'options':'-csearch_path='+schema})
    from app.database import migrate
    migrate(scoped);migrate(scoped)
    monkeypatch.setenv('DATABASE_URL',scoped)
    yield DrawRepository(tmp_path/'postgres')
    with psycopg.connect(url,autocommit=True) as con:
        con.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))


def test_postgres_migration_raw_roundtrip_snapshots_and_lock(postgres):
    raw=postgres.archive('test-source',200,b'{"unchanged":true}',AT)
    assert raw['raw_path'].startswith('db:')
    assert postgres.read_raw(raw['raw_path'])==b'{"unchanged":true}'
    assert postgres.cached_raw('test-source')['raw_path']==raw['raw_path']
    assert postgres.cached_raw('test-source',AT+timedelta(seconds=1)) is None
    d=draw();postgres.save_draw(d,AT);postgres.save_draw(d,AT)
    assert postgres.counts()['stryktipset_matches']==13
    assert postgres.counts()['crowd_snapshots']==13
    assert postgres.pre_close(4970)
    assert len(postgres.inputs_asof(4970,AT)[0])==13
    with postgres.lock('test') as first:
        assert first
        with postgres.lock('test') as second:
            assert not second
    with postgres.lock('test') as third:
        assert third


def test_postgres_collection_roundtrip(postgres,service):
    service.repo=postgres
    service.provider.repo=postgres
    service.market=MarketService(postgres,MarketConfig())
    run=collect(service,force=True)
    assert run['prediction_status']['saved']==13,run
    assert postgres.counts()['optimizer_snapshots']==1
    with postgres.connection() as con:
        assert json.loads(con.execute('SELECT payload FROM collection_runs').fetchone()[0])['run_id']==run['run_id']
