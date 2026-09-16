from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict
from app.news.service import NewsService
from app.schemas import Coupon

router = APIRouter()


class UpdateNewsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    coupon: Coupon | None = None


def cutoff(as_of: datetime | None) -> datetime | None:
    if as_of and not as_of.tzinfo:
        raise HTTPException(422, "as_of måste inkludera tidszon.")
    if as_of and as_of > datetime.now(timezone.utc):
        raise HTTPException(422, "as_of får inte ligga i framtiden.")
    return as_of


@router.get("/api/news/status")
def news_status() -> dict:
    return NewsService().status()


@router.get("/api/matches/{identifier}/news")
def match_news(identifier: str, as_of: datetime | None = None) -> dict:
    return NewsService().view(identifier, cutoff(as_of))


@router.get("/api/matches/{identifier}/news/signals")
def match_signals(identifier: str, as_of: datetime | None = None) -> list[dict]:
    return NewsService().view(identifier, cutoff(as_of))["signals"]


@router.get("/api/matches/{identifier}/news/sources")
def match_sources(identifier: str, as_of: datetime | None = None) -> list[dict]:
    return NewsService().view(identifier, cutoff(as_of))["sources"]


@router.post("/api/news/update")
def update_news(body: UpdateNewsRequest, request: Request) -> dict:
    if request.client and request.client.host not in ("127.0.0.1", "::1", "testclient"):
        raise HTTPException(403, "Nyhetsuppdatering är endast tillgänglig lokalt.")
    # Reject cross-site browser writes even when the service is listening on localhost.
    origin = request.headers.get("origin")
    if origin and origin not in ("http://127.0.0.1:4200", "http://localhost:4200", "http://127.0.0.1:8000", "http://localhost:8000"):
        raise HTTPException(403, "Otillåtet ursprung.")
    service = NewsService()
    saved = service.repo.current_coupon()
    coupon = body.coupon or (Coupon.model_validate(saved) if saved else None)
    if coupon is None:
        raise HTTPException(422, "Analysera eller ange en kupong först.")
    try:
        return service.update(coupon)
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from None
    except ValueError:
        raise HTTPException(503, "Nyhetsextraktionen är inte korrekt konfigurerad. Kontrollera provider, LLM_API_KEY och LLM_MODEL.") from None


@router.get("/api/coupon/manual/current")
def current_coupon() -> dict | None:
    return NewsService().repo.current_coupon()


@router.get("/api/coupon/{identifier}/snapshots")
def coupon_snapshots(identifier: str) -> list[dict]:
    return NewsService().repo.coupon_history(identifier)
