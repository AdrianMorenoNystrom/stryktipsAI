"""News settings are read at service construction, with no secrets in status/logs."""
import os
from dataclasses import dataclass, field
from pathlib import Path
from app.config import ROOT

QUERY_TEMPLATES = ('"{team}" team news injuries suspension', '"{team}" training press conference rotation predicted lineup')
MATCH_QUERY = '"{home}" "{away}" team news injuries'
SOURCE_QUALITY = {1: 1.0, 2: .85, 3: .65, 4: .4}
RSS_FEEDS = ("https://feeds.bbci.co.uk/sport/football/rss.xml", "https://www.skysports.com/rss/11095")
TEAM_FEED_SLUGS = {"Manchester United": "manchester-united", "Manchester City": "manchester-city",
    "Brighton": "brighton-and-hove-albion", "Newcastle": "newcastle-united", "Leeds": "leeds-united",
    "West Ham": "west-ham-united", "Coventry": "coventry-city", "Hull": "hull-city", "Norwich": "norwich-city",
    "West Brom": "west-bromwich-albion", "QPR": "queens-park-rangers", "Preston": "preston-north-end",
    "Stoke": "stoke-city", "Blackburn": "blackburn-rovers", "Bolton": "bolton-wanderers"}


@dataclass
class NewsConfig:
    provider: str = field(default_factory=lambda: os.getenv("NEWS_PROVIDER", "").lower())
    api_key: str = field(default_factory=lambda: os.getenv("NEWS_API_KEY", ""), repr=False)
    llm_key: str = field(default_factory=lambda: os.getenv("LLM_API_KEY", os.getenv("OPENAI_API_KEY", "")), repr=False)
    llm_model: str = field(default_factory=lambda: os.getenv("LLM_MODEL", ""))
    extraction: str = field(default_factory=lambda: os.getenv("NEWS_EXTRACTION", "rules").lower())
    root: Path = field(default_factory=lambda: Path(os.getenv("STRYKTIPS_NEWS_DIR") or ROOT / "data" / "news"))
    lookback_days: int = 7
    cache_seconds: int = 3600
    request_interval: float = 1.0
    max_results: int = 8
    max_queries: int = 80
    allowed_tiers: tuple[int, ...] = (1, 2, 3, 4)
    story_similarity: float = .82
    story_hours: int = 72
    strong_confidence: float = .80
    uncertain_confidence: float = .60
    feeds: tuple[str, ...] = RSS_FEEDS

    @property
    def configured(self) -> bool:
        return self.provider == "rss" or (self.provider in ("brave", "tavily") and bool(self.api_key))

    def public_status(self) -> dict:
        extraction_configured = self.extraction == "rules" or (self.extraction == "openai" and bool(self.llm_key and self.llm_model))
        return {"configured": self.configured, "provider": self.provider or None,
                "extraction": self.extraction, "extractionConfigured": extraction_configured,
                "newsAffectsProbabilities": False,
                "message": None if self.configured else "News Intelligence är inte konfigurerat. Välj RSS eller konfigurera nyhetsprovider i miljön."}
