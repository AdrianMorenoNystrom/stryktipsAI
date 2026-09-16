from datetime import datetime, timezone
from typing import Literal
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import Field
from app.schemas import Schema, Odds
from app.storage import now_utc
from app.stryktipset.parser import ProviderSchemaError
from app.stryktipset.provider import ProviderUnavailable
from app.stryktipset.service import DrawNotReady, DrawService
from app.stryktipset.teams import save_alias

router=APIRouter()


def local(request: Request):
    from app.runtime import Runtime
    runtime=Runtime.load()
    if runtime.production:
        if request.headers.get('origin') and request.headers['origin'] not in runtime.origins:
            raise HTTPException(403,'Otillåtet ursprung.')
        return  # Shared mutations require admin authorization in API middleware.
    if request.client and request.client.host not in ('127.0.0.1','::1','testclient'):
        raise HTTPException(403,"Endast lokal uppdatering är tillåten.")
    origin=request.headers.get('origin')
    if origin and origin not in ('http://localhost:4200','http://127.0.0.1:4200','http://localhost:8000','http://127.0.0.1:8000'):
        raise HTTPException(403,"Otillåtet ursprung.")


def cutoff(value: datetime | None):
    if value and (not value.tzinfo or value>now_utc()):
        raise HTTPException(422,"as_of måste ha tidszon och får inte ligga i framtiden.")
    return value


class LiveAnalysisRequest(Schema):
    drawNumber: int | None = None
    budget: float = Field(default=256,ge=1,le=1000000)
    mode: Literal['optimal','safe','value'] = 'optimal'


class ManualOddsRequest(Schema):
    odds: dict[int,Odds]


class AliasRequest(Schema):
    alias: str = Field(min_length=1,max_length=100)
    canonical: str = Field(min_length=1,max_length=100)


@router.get('/api/coupon/current')
def current(draw_number: int | None = Query(default=None,gt=0)):
    return DrawService().current(draw_number=draw_number)


@router.post('/api/coupon/current/refresh')
def refresh(request: Request, draw_number: int | None = Query(default=None,gt=0)):
    local(request)
    return DrawService().current(refresh=True,draw_number=draw_number)


@router.post('/api/coupon/current/analyze')
def analyze_current(body: LiveAnalysisRequest):
    try:
        return DrawService().analyze_live(body.drawNumber,body.budget,body.mode)
    except DrawNotReady as exc:
        raise HTTPException(422,str(exc)) from None


@router.get('/api/stryktipset/status')
def status():
    service=DrawService()
    return {**service.repo.health(),"counts":service.repo.counts(),"enabled":service.config.enabled}


@router.get('/api/stryktipset/draws')
def draws():
    return DrawService().archive()


@router.get('/api/stryktipset/draws/{draw_number}')
def draw_history(draw_number: int, selection: Literal['pre_close','first','24h','latest']='pre_close', as_of: datetime | None=None):
    try:
        return DrawService().history(draw_number,selection,cutoff(as_of))
    except DrawNotReady as exc:
        raise HTTPException(404,str(exc)) from None


@router.get('/api/stryktipset/draws/{draw_number}/matches/{number}/crowd')
def crowd_history(draw_number: int,number: int,as_of: datetime | None=None):
    from app.stryktipset.service import movements
    rows=DrawService().repo.crowd_history(draw_number,number,cutoff(as_of) or now_utc())
    return {"history":rows,"movement":movements(rows)}


@router.post('/api/stryktipset/draws/{draw_number}/odds')
def manual_odds(draw_number: int,body: ManualOddsRequest,request: Request):
    local(request)
    service=DrawService()
    draw=service.repo.draw(draw_number)
    if not draw or draw.sales_close_at<=now_utc():
        raise HTTPException(422,"Välj en sparad omgång före spelstopp.")
    if not body.odds or any(n<1 or n>13 for n in body.odds):
        raise HTTPException(422,"Ange odds för matchnummer 1–13.")
    service.repo.save_manual_odds(draw,{n:p.model_dump() for n,p in body.odds.items()},now_utc())
    return service.current(draw_number=draw_number)


@router.post('/api/stryktipset/draws/{draw_number}/results/refresh')
def result_refresh(draw_number: int,request: Request):
    local(request)
    try:
        return DrawService().update_results(draw_number)
    except DrawNotReady as exc:
        raise HTTPException(422,str(exc)) from None
    except (ProviderUnavailable,ProviderSchemaError) as exc:
        raise HTTPException(503,str(exc)) from None


@router.post('/api/teams/aliases')
def create_alias(body:AliasRequest,request:Request):
    local(request)
    from app.runtime import Runtime
    if Runtime.load().production:
        raise HTTPException(409,'Produktionsalias ändras i den versionshanterade lagmappningen och deployas tillsammans med appen.')
    try:
        return save_alias(body.alias,body.canonical)
    except ValueError as exc:
        raise HTTPException(422,str(exc)) from None


@router.get('/api/stryktipset/draws/{draw_number}/matches/{number}/market')
def market_history(draw_number:int,number:int,as_of:datetime | None=None):
    service=DrawService()
    at=cutoff(as_of) or now_utc()
    rows=service.market.history(draw_number,number,at)
    crowd=service.repo.crowd_history(draw_number,number,at)
    with service.repo.connection() as con:
        predictions=con.execute('SELECT payload FROM prediction_snapshots WHERE draw_number=? AND number=? AND predicted_at<=? ORDER BY predicted_at',(draw_number,number,at.isoformat())).fetchall()
    import json
    return {'market':rows,'crowd':crowd,'predictions':[{'id':p['id'],'predicted_at':p['predicted_at'],'model':p['match']['model']} for r in predictions for p in [json.loads(r[0])]]}
