"""Public draw ingestion settings; independent of the scheduler and prediction model."""
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from app.config import ROOT

STOCKHOLM = ZoneInfo("Europe/Stockholm")
PROVIDER = "svenska-spel"
BASE_URL = "https://api.spela.svenskaspel.se/draw/1/stryktipset"
PARSER_VERSION = "1.0"


@dataclass
class DrawConfig:
    root: Path = field(default_factory=lambda: Path(os.getenv("STRYKTIPS_LIVE_DIR") or ROOT / "data" / "stryktipset"))
    enabled: bool = field(default_factory=lambda: os.getenv("STRYKTIPS_LIVE_ENABLED", "true").lower() == "true")
    request_interval: float = 1.0
    timeout: float = 20
    retries: int = 3
    manual_refresh_min_seconds: int = 60
    failure_retry_seconds: int = 300
    early_interval_seconds: int = 6 * 3600
    friday_interval_seconds: int = 2 * 3600
    matchday_interval_seconds: int = 3600
    close_interval_seconds: int = 1800
    close_window_seconds: int = 6 * 3600
    final_window_seconds: int = 30 * 60
    final_interval_seconds: int = 5 * 60
    max_import_draws: int = 500

    def interval(self, now: datetime, sales_close: datetime | None) -> int:
        local = now.astimezone(STOCKHOLM)
        if sales_close:
            remaining = (sales_close - now).total_seconds()
            if 0 < remaining <= self.final_window_seconds:
                return self.final_interval_seconds
            if 0 < remaining <= self.close_window_seconds:
                return self.close_interval_seconds
            if 0 < remaining <= 24 * 3600:
                return self.matchday_interval_seconds
            if 0 < remaining <= 48 * 3600:
                return self.friday_interval_seconds
        return self.early_interval_seconds
