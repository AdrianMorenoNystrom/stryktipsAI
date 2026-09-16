import json
import logging
from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from app.config import BUDGET_PRESETS, CROWD_TOLERANCE, DATA, LEAGUES, ROW_COST, VALUE_FLOOR
from app.demo import demo_coupon
from app.schemas import AnalyzeRequest, CostRequest, MatchInput
from app.services.coupon import analyze
from app.services.optimizer import system_cost
from app.services.teams import key, normalize_team
from ml.predict import PredictionService
from app.news.api import router as news_router
from app.news.service import NewsService
from app.news.repository import now_utc
from app.stryktipset.api import router as draw_router
from app.stryktipset.service import DrawService, DrawNotReady
from fastapi import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from app.runtime import Runtime
import os
import secrets

runtime = Runtime.load()

app = FastAPI(title="Stryktipset Predictor", version="0.4.0")
app.add_middleware(CORSMiddleware,allow_origins=list(runtime.origins),allow_methods=['GET','POST'],allow_headers=['Content-Type'],allow_credentials=False)
app.include_router(news_router)
app.include_router(draw_router)
predictor = PredictionService()


@app.middleware('http')
async def production_writes(request: Request, call_next):
    if runtime.production and request.method not in ('GET','HEAD','OPTIONS'):
        public = ('/api/coupon/analyze','/api/coupon/optimize','/api/coupon/cost','/api/predict/match','/api/coupon/current/analyze','/api/coupon/current/refresh')
        if request.url.path not in public:
            token = os.getenv('ADMIN_API_TOKEN','')
            if not token or not secrets.compare_digest(request.headers.get('x-admin-token',''),token):
                return JSONResponse(status_code=403,content={'detail':'Administratörsåtkomst krävs för gemensamma dataändringar.'})
        if request.headers.get('origin') and request.headers['origin'] not in runtime.origins:
            return JSONResponse(status_code=403,content={'detail':'Otillåtet ursprung.'})
    return await call_next(request)


@app.get('/health')
def health():
    try:
        service=DrawService(predictor=predictor)
        with service.repo.connection() as con:
            con.execute('SELECT 1').fetchone()
            last=con.execute('SELECT payload FROM collection_runs ORDER BY started_at DESC LIMIT 1').fetchone()
        return {'api':'healthy','database':'postgres' if service.repo.database_url else 'sqlite',
            'svenska_spel_provider':service.repo.health('https://api.spela.svenskaspel.se/draw/1/stryktipset/draws'),
            'odds_provider':service.market.health(),'last_collection':json.loads(last[0]) if last else None}
    except Exception:
        return JSONResponse(status_code=503,content={'api':'degraded','database':'unavailable'})


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = [{"field": ".".join(str(p) for p in e["loc"] if p != "body"), "message": e["msg"]} for e in exc.errors()]
    return JSONResponse(status_code=422, content={"message": "Kontrollera kupongens inmatning.", "errors": errors})


@app.get("/api/config")
def config() -> dict:
    return {"budgetPresets": BUDGET_PRESETS, "costPerRow": ROW_COST, "leagues": LEAGUES,
            "environment":runtime.environment,"demoEnabled":not runtime.production,
            "crowdTolerance": CROWD_TOLERANCE, "valueFloor": VALUE_FLOOR}


@app.get("/api/model/status")
def status() -> dict:
    result = predictor.status()
    report = DATA / "download_report.json"
    result["importReport"] = json.loads(report.read_text(encoding="utf-8")) if report.exists() else None
    return result


@app.get("/api/teams/search")
def teams(q: str = Query(default="", max_length=100)) -> list[dict]:
    predictor.load()
    if not predictor.bundle:
        return []
    if predictor.bundle['state'] is None:
        from app.stryktipset.teams import canonical_names
        return [{'id':identifier,'name':name} for identifier,name in sorted(canonical_names().items(),key=lambda item:item[1]) if key(q) in key(name)][:100]
    # Team display names are persisted in match history as opponents.
    names = {r["opponent"] for state in predictor.bundle["state"].teams.values() for r in state.history}
    return [{"id": key(name), "name": name} for name in sorted(names) if key(normalize_team(q)) in key(name)][:100]


@app.get("/api/coupon/demo")
def demo() -> dict:
    if runtime.production:
        raise HTTPException(404,'Demo är inte tillgänglig i produktion.')
    return demo_coupon()


@app.post("/api/predict/match")
def predict_match(match: MatchInput) -> dict:
    return predictor.predict(match)


@app.post("/api/coupon/analyze")
def analyze_coupon(request: AnalyzeRequest) -> dict:
    if runtime.production and request.coupon.demo:
        raise HTTPException(422,'Demo kan inte analyseras i produktionsläget.')
    if request.coupon.drawNumber is not None:
        return analyze_live_coupon(request)
    save_coupon_snapshot(request)
    return analyze(request, predictor)


@app.post("/api/coupon/optimize")
def optimize_coupon(request: AnalyzeRequest) -> dict:
    if runtime.production and request.coupon.demo:
        raise HTTPException(422,'Demo kan inte analyseras i produktionsläget.')
    if request.coupon.drawNumber is not None:
        return analyze_live_coupon(request)
    save_coupon_snapshot(request)
    return analyze(request, predictor)


def analyze_live_coupon(request: AnalyzeRequest) -> dict:
    try:
        result = DrawService(predictor=predictor).analyze_live(request.coupon.drawNumber,request.budget,request.mode)
        save_coupon_snapshot(AnalyzeRequest(coupon=result['inputCoupon'],budget=request.budget,mode=request.mode))
        return result
    except DrawNotReady as exc:
        raise HTTPException(422,str(exc)) from None


def save_coupon_snapshot(request: AnalyzeRequest) -> None:
    if runtime.production:
        return  # Live predictions already reference the durable draw archive.
    try:
        NewsService().repo.save_coupon(request.coupon.model_dump(mode="json"), now_utc())
    except Exception:
        # News/storage outages must never prevent probability computation.
        logging.exception("Coupon snapshot persistence failed; prediction remains available")


@app.post("/api/coupon/cost")
def cost(request: CostRequest) -> dict:
    return system_cost(request.selections)
