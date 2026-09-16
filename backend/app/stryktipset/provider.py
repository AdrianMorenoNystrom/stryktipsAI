"""Read-only public HTTP adapter. No login, cookies, account or purchase methods."""
from datetime import datetime, timedelta
import json
import logging
import time
from typing import Protocol
import httpx
from app.storage import now_utc
from app.stryktipset.config import BASE_URL, DrawConfig
from app.stryktipset.parser import ProviderSchemaError, draw_objects, parse_draw, parse_result
from app.stryktipset.repository import DrawRepository
from app.stryktipset.schemas import Draw, DrawResult

log = logging.getLogger(__name__)


class CouponProvider(Protocol):
    def get_current_draw(self, refresh: bool = False) -> list[Draw]: ...
    def get_draw(self, draw_number: int, refresh: bool = False) -> Draw: ...
    def get_results(self, draw_number: int, refresh: bool = False) -> DrawResult: ...


class ProviderUnavailable(RuntimeError):
    pass


class SvenskaSpelProvider:
    def __init__(self, config: DrawConfig, repo: DrawRepository, client: httpx.Client | None = None):
        self.config, self.repo = config, repo
        self.client = client
        self.last_request = 0.0

    def fetch(self, suffix: str, refresh: bool = False, historical: bool = False) -> tuple[dict, dict]:
        source = BASE_URL + "/" + suffix
        cached = None if refresh else self.repo.cached_raw(source, None if historical else now_utc() - timedelta(seconds=self.config.manual_refresh_min_seconds))
        if cached:
            return self.decode(self.repo.read_raw(cached['raw_path'])), cached
        if not self.config.enabled:
            raise ProviderUnavailable("Svenska Spel-hämtning är avstängd i konfigurationen.")
        for attempt in range(self.config.retries):
            time.sleep(max(0, self.config.request_interval - (time.monotonic() - self.last_request)))
            self.last_request = time.monotonic()
            try:
                if self.client:
                    response = self.client.get(source)
                else:
                    with httpx.Client(timeout=self.config.timeout, follow_redirects=False, headers={"Accept":"application/json","User-Agent":"StryktipsetPredictor/0.3 public-read-only"}) as client:
                        response = client.get(source)
                retrieved = now_utc()
                raw = self.repo.archive(source,response.status_code,response.content,retrieved)
                if response.status_code in (429,500,502,503,504) and attempt + 1 < self.config.retries:
                    wait = response.headers.get("Retry-After", "")
                    time.sleep(min(float(wait),10) if wait.isdigit() else 2 ** attempt)
                    continue
                if response.status_code != 200:
                    raise ProviderUnavailable(f"Svenska Spel HTTP {response.status_code}")
                return self.decode(response.content), raw
            except httpx.HTTPError:
                if attempt + 1 == self.config.retries:
                    self.repo.record_health(False,source,"provider_connection_error",now_utc())
                    raise ProviderUnavailable("Svenska Spel kunde inte nås.") from None
                time.sleep(2 ** attempt)
        raise ProviderUnavailable("Svenska Spel kunde inte nås.")

    @staticmethod
    def decode(raw: bytes) -> dict:
        try:
            result = json.loads(raw)
            if not isinstance(result,dict):
                raise ValueError()
            return result
        except (ValueError, UnicodeError):
            raise ProviderSchemaError("provider_schema_error: invalid JSON object") from None

    def _run(self, suffix: str, parser, refresh=False, historical=False):
        source = BASE_URL + "/" + suffix
        try:
            payload, raw = self.fetch(suffix,refresh,historical)
            result = parser(payload,datetime.fromisoformat(raw['retrieved_at']),source,raw['id'])
            self.repo.record_health(True,source,None,datetime.fromisoformat(raw['retrieved_at']))
            return result
        except (ProviderUnavailable, ProviderSchemaError) as exc:
            issue = f"provider_schema_error: {exc}" if isinstance(exc,ProviderSchemaError) else str(exc)
            self.repo.record_health(False,source,issue,now_utc())
            log.warning("%s: %s",source,issue)
            raise

    def get_current_draw(self, refresh=False) -> list[Draw]:
        return self._run("draws", lambda payload,at,source,raw_id: [parse_draw(raw,at,source,raw_id) for raw in draw_objects(payload)],refresh=refresh)

    def get_draw(self, draw_number: int, refresh=False) -> Draw:
        def parse(payload,at,source,raw_id):
            draw = parse_draw(draw_objects(payload,True)[0],at,source,raw_id)
            if draw.draw_number != draw_number:
                raise ProviderSchemaError("Requested draw does not match response")
            return draw
        return self._run(f"draws/{draw_number}",parse,refresh,historical=True)

    def get_results(self, draw_number: int, refresh=False) -> DrawResult:
        return self._run(f"draws/{draw_number}/result",lambda payload,at,source,raw_id:parse_result(payload,at,source,raw_id,draw_number),refresh,historical=True)
