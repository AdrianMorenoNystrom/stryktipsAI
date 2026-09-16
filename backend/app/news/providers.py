"""Provider boundaries preserve raw response bytes and never log authentication."""
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import json
import re
import time
from typing import Protocol
import xml.etree.ElementTree as ET
import httpx
from app.news.config import NewsConfig, TEAM_FEED_SLUGS
from app.services.teams import normalize_team


def parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        try:
            value = value.replace(" BST", " +0100")
            parsed = parsedate_to_datetime(value)
        except (ValueError, TypeError, OverflowError):
            return None
    # A date-only result cannot be used as a precise publication timestamp.
    return parsed.astimezone(timezone.utc) if parsed.tzinfo else None


@dataclass
class SearchResult:
    articles: list[dict]
    raw: bytes
    source: str


class NewsProvider(Protocol):
    def search(self, query: str, from_time: datetime, to_time: datetime) -> list[SearchResult]: ...


class ProviderError(RuntimeError):
    pass


class HttpProvider:
    def __init__(self, config: NewsConfig, client: httpx.Client | None = None) -> None:
        self.config = config
        self.client = client or httpx.Client(timeout=30, follow_redirects=True)
        self.last_request = 0.0
        self.request_count = 0

    def request(self, method: str, url: str, **kwargs) -> httpx.Response:
        for attempt in range(3):
            elapsed = time.monotonic() - self.last_request
            if elapsed < self.config.request_interval:
                time.sleep(self.config.request_interval - elapsed)
            self.last_request = time.monotonic()
            self.request_count += 1
            try:
                response = self.client.request(method, url, **kwargs)
            except httpx.HTTPError as exc:
                if attempt == 2:
                    raise ProviderError(f"Provider connection failed ({type(exc).__name__})") from None
                time.sleep(2 ** attempt)
                continue
            if response.status_code == 429 or response.status_code >= 500:
                if attempt < 2:
                    retry_after = response.headers.get("Retry-After", "")
                    time.sleep(min(float(retry_after), 10) if retry_after.isdigit() else 2 ** attempt)
                    continue
            if response.status_code >= 400:
                raise ProviderError(f"Provider returned HTTP {response.status_code}")
            return response
        raise ProviderError("Provider exhausted retries")


class TavilyProvider(HttpProvider):
    def search(self, query: str, from_time: datetime, to_time: datetime) -> list[SearchResult]:
        response = self.request("POST", "https://api.tavily.com/search", headers={"Authorization": f"Bearer {self.config.api_key}"},
            json={"query": query, "topic": "news", "max_results": self.config.max_results,
                  "start_date": from_time.date().isoformat(), "end_date": to_time.date().isoformat(),
                  "include_raw_content": "text", "include_answer": False})
        results = [{"title": r.get("title", ""), "url": r["url"], "published_at": r.get("published_date"),
                    "snippet": r.get("content", ""), "content": r.get("raw_content") or ""} for r in response.json().get("results", [])]
        return [SearchResult(results, response.content, "tavily")]


class BraveProvider(HttpProvider):
    def search(self, query: str, from_time: datetime, to_time: datetime) -> list[SearchResult]:
        response = self.request("GET", "https://api.search.brave.com/res/v1/news/search", headers={"X-Subscription-Token": self.config.api_key},
            params={"q": query, "count": self.config.max_results, "freshness": f"{from_time:%Y-%m-%d}to{to_time:%Y-%m-%d}", "extra_snippets": "true"})
        results = [{"title": r.get("title", ""), "url": r["url"],
                    "published_at": datetime.fromtimestamp(r["page_age"], timezone.utc).isoformat() if isinstance(r.get("page_age"), (int, float)) else r.get("page_age"),
                    "snippet": r.get("description", ""), "content": "\n".join(r.get("extra_snippets", []))} for r in response.json().get("results", [])]
        return [SearchResult(results, response.content, "brave")]


class RssProvider(HttpProvider):
    def __init__(self, config: NewsConfig, client: httpx.Client | None = None) -> None:
        super().__init__(config, client)
        self.feeds_cache: dict[str, SearchResult | None] = {}
        self.failures: list[str] = []

    def search(self, query: str, from_time: datetime, to_time: datetime) -> list[SearchResult]:
        # One fetch per feed per job, not one fetch per team/query. Pipeline applies team/time filters.
        teams = [normalize_team(name) for name in re.findall(r'"([^"]+)"', query)]
        urls = [*self.config.feeds, *[f"https://feeds.bbci.co.uk/sport/football/teams/{TEAM_FEED_SLUGS.get(name, name.lower().replace(' ', '-'))}/rss.xml" for name in teams]]
        for url in urls:
            if url not in self.feeds_cache:
                try:
                    response = self.request("GET", url)
                    root = ET.fromstring(response.content)
                    articles = [{"title": item.findtext("title", ""), "url": item.findtext("link", ""),
                                 "published_at": item.findtext("pubDate"), "snippet": item.findtext("description", ""), "content": ""}
                                for item in root.findall(".//item")]
                    self.feeds_cache[url] = SearchResult(articles, response.content, url)
                except (ProviderError, ET.ParseError) as exc:
                    self.failures.append(f"RSS feed failed: {url} ({type(exc).__name__})")
                    self.feeds_cache[url] = None
        results = [self.feeds_cache[url] for url in urls if self.feeds_cache.get(url) is not None]
        if not results:
            raise ProviderError("No RSS feeds could be fetched")
        return results


def create_provider(config: NewsConfig) -> NewsProvider:
    if not config.configured:
        raise ProviderError("News provider is not configured")
    return {"rss": RssProvider, "brave": BraveProvider, "tavily": TavilyProvider}[config.provider](config)
