from collections import Counter
from datetime import datetime, timedelta, timezone
import hashlib
import json
import logging
import re
from threading import Lock

from app.news.config import MATCH_QUERY, QUERY_TEMPLATES, NewsConfig
from app.news.entities import canonical_url, detected_teams, digest, mentions, publisher_info
from app.news.events import active_signals, record_signal
from app.news.extraction import create_extractor
from app.news.providers import ProviderError, create_provider, parse_time
from app.news.repository import NewsRepository, now_utc
from app.news.schemas import Extraction, NewsArticle
from app.schemas import Coupon
from app.services.match_identity import match_id
from app.services.teams import normalize_team, team_id

log = logging.getLogger(__name__)
UPDATE_LOCK = Lock()


def queries_for_coupon(coupon: Coupon) -> list[str]:
    teams = sorted({normalize_team(name) for match in coupon.matches for name in (match.homeTeam, match.awayTeam)})
    return list(dict.fromkeys([template.format(team=team) for team in teams for template in QUERY_TEMPLATES]
                            + [MATCH_QUERY.format(home=normalize_team(m.homeTeam), away=normalize_team(m.awayTeam)) for m in coupon.matches]))


class NewsService:
    def __init__(self, config: NewsConfig | None = None, provider=None, extractor=None) -> None:
        self.config = config or NewsConfig()
        self.repo = NewsRepository(self.config.root)
        self.provider = provider
        self.extractor = extractor

    def status(self) -> dict:
        return {**self.config.public_status(), "counts": self.repo.counts(), "lastRun": self.repo.latest_run()}

    def view(self, identifier: str, as_of: datetime | None = None) -> dict:
        as_of = (as_of or now_utc()).astimezone(timezone.utc)
        snapshot = self.repo.snapshot(identifier, as_of)
        signals = snapshot["signals"] if snapshot else []
        sources = self.repo.match_sources(identifier, as_of)
        evidence_ids = list({version for signal in signals for version in signal.get("source_article_ids", [])})
        # Keep the exact cited version even when a newer article version exists.
        sources = list({a["version_id"]: a for a in [*sources, *self.repo.article_sources(evidence_ids, as_of)]}.values())
        last_run = self.repo.latest_run()
        error = None
        if last_run and identifier in last_run.get("failed_matches", []) and datetime.fromisoformat(last_run["checked_at"]) <= as_of:
            error = "Nyhetsuppdateringen kunde inte slutföras. Senast sparad information visas."
        return {**self.config.public_status(), "match_id": identifier, "as_of": as_of.isoformat(),
                "last_checked_at": snapshot["snapshot_time"] if snapshot else None,
                "signals": signals, "sources": sources, "source_count": len({a["publisher"] for a in sources}),
                "error": error, "stale": bool(snapshot and (as_of - datetime.fromisoformat(snapshot["snapshot_time"])).total_seconds() > 86400)}

    def update(self, coupon: Coupon, at: datetime | None = None) -> dict:
        # 'at' is injectable for deterministic tests, never accepted from the public update API.
        at = (at or now_utc()).astimezone(timezone.utc)
        public = self.config.public_status()
        if not public["configured"]:
            return {**public, "queries": 0, "articles_fetched": 0, "signals_extracted": 0}
        if not UPDATE_LOCK.acquire(blocking=False):
            raise RuntimeError("En nyhetsuppdatering pågår redan.")
        try:
            return self._update(coupon, at)
        finally:
            UPDATE_LOCK.release()

    def _update(self, coupon: Coupon, at: datetime) -> dict:
        provider = self.provider or create_provider(self.config)
        extractor = self.extractor or create_extractor(self.config)
        self.repo.save_coupon(coupon.model_dump(mode="json"), at)
        teams = sorted({normalize_team(name) for match in coupon.matches for name in (match.homeTeam, match.awayTeam)})
        queries = queries_for_coupon(coupon)[:self.config.max_queries]
        identifiers = {match_id(match): match for match in coupon.matches}
        from_time = at - timedelta(days=self.config.lookback_days)
        report = {"configured": True, "provider": self.config.provider, "extractor": extractor.version,
                  "checked_at": at.isoformat(), "coupon_id": coupon.id, "demo_fixture_context": coupon.demo,
                  "queries": len(queries), "cached_queries": 0, "articles_fetched": 0, "unique_articles": 0,
                  "articles_created": 0, "articles_deduplicated": 0, "events_created": 0, "signals_extracted": 0,
                  "observations_created": 0, "matches_updated": 0, "matches_with_signals": 0,
                  "failed_requests": [], "failed_matches": [], "extraction_failures": 0,
                  "articles_irrelevant": 0, "articles_missing_timestamp": 0, "articles_outside_window": 0}
        before = self.repo.counts()
        articles: dict[str, NewsArticle] = {}
        raw_items_seen = set()
        for query in queries:
            log.info("News query: %s", query)
            cache_key = digest("scoped-rss-v2" + self.config.provider + query + from_time.date().isoformat() + at.date().isoformat())
            try:
                responses = self.repo.cache_get(cache_key, at - timedelta(seconds=self.config.cache_seconds))
                if responses is None:
                    responses = []
                    for response in provider.search(query, from_time, at):
                        raw_path = self.repo.save_raw(response.raw)
                        responses.append({"articles": response.articles, "raw_path": raw_path, "retrieved_at": at.isoformat()})
                    self.repo.cache_put(cache_key, at, responses)
                else:
                    report["cached_queries"] += 1
                for response in responses:
                    for item in response["articles"]:
                        text = "\n".join([item.get("title", ""), item.get("snippet", ""), item.get("content", "")])
                        detected = detected_teams(text, teams)
                        if not detected:
                            continue
                        raw_item_key = (response["raw_path"], digest(json.dumps(item, sort_keys=True)))
                        if raw_item_key not in raw_items_seen:
                            report["articles_fetched"] += 1
                            raw_items_seen.add(raw_item_key)
                        url = canonical_url(item["url"])
                        publisher, tier = publisher_info(url)
                        if tier not in self.config.allowed_tiers:
                            continue
                        published = parse_time(item.get("published_at"))
                        fingerprint = hashlib.sha256((text + str(published)).encode()).hexdigest()
                        article = NewsArticle(id=digest(url), version_id=digest(url + fingerprint), title=item.get("title", ""), url=url,
                            publisher=publisher, source_tier=tier, published_at=published, retrieved_at=datetime.fromisoformat(response["retrieved_at"]),
                            content=item.get("content", ""), snippet=item.get("snippet", ""), detected_team_ids=detected,
                            query=query, raw_path=response["raw_path"], content_hash=hashlib.sha256(text.encode()).hexdigest())
                        if article.version_id in articles:
                            report["articles_deduplicated"] += 1
                            continue
                        articles[article.version_id] = article
                        report["articles_created"] += int(self.repo.save_article(article))
            except (ProviderError, ValueError, KeyError, TypeError) as exc:
                report["failed_requests"].append({"query": query, "error": type(exc).__name__})
                # Only matches whose teams were included in the failed query are marked partial.
                report["failed_matches"].extend(identifier for identifier, match in identifiers.items()
                    if mentions(query, match.homeTeam) or mentions(query, match.awayTeam))
        report["unique_articles"] = len({a.id for a in articles.values()})
        report["articles_deduplicated"] = report["articles_fetched"] - len(articles)
        report["provider_requests"] = getattr(provider, "request_count", 0)
        for article in articles.values():
            if article.published_at is None:
                report["articles_missing_timestamp"] += 1
                continue
            if not from_time <= article.published_at <= at:
                report["articles_outside_window"] += 1
                continue
            for identifier, match in identifiers.items():
                if any(team_id(name) in article.detected_team_ids for name in (match.homeTeam, match.awayTeam)) and at.date() < match.date:
                    self.repo.link_article(identifier, article.version_id, at)
            try:
                cached_extraction = self.repo.extraction(article.version_id, extractor.version)
                extraction = Extraction.model_validate(cached_extraction) if cached_extraction is not None else extractor.extract(article, teams)
                if cached_extraction is None:
                    self.repo.save_extraction(article.version_id, extractor.version, extraction.model_dump(mode="json"), at)
                if not extraction.signals:
                    report["articles_irrelevant"] += 1
                report["signals_extracted"] += len(extraction.signals)
                for signal in extraction.signals:
                    for identifier, match in identifiers.items():
                        # Date-only fixtures use UTC start of day as conservative pre-match cutoff.
                        kickoff = datetime.combine(match.date, datetime.min.time(), tzinfo=timezone.utc)
                        if team_id(signal.team) in (team_id(match.homeTeam), team_id(match.awayTeam)) and at < kickoff and article.published_at < kickoff:
                            report["observations_created"] += int(record_signal(self.repo, self.config, article, signal, identifier, at, extractor.version))
            except (ValueError, TypeError, KeyError, ProviderError) as exc:
                report["extraction_failures"] += 1
                report["failed_matches"].extend(identifier for identifier, match in identifiers.items()
                    if team_id(match.homeTeam) in article.detected_team_ids or team_id(match.awayTeam) in article.detected_team_ids)
                log.warning("News extraction rejected for article %s (%s)", article.id, type(exc).__name__)
        feed_failures = getattr(provider, "failures", [])
        report["failed_requests"].extend({"query": "RSS feed", "error": failure} for failure in feed_failures)
        if feed_failures:
            # Shared feeds can contain any coupon team: flag incomplete coverage conservatively.
            report["failed_matches"].extend(identifiers)
        report["failed_matches"] = sorted(set(report["failed_matches"]))
        all_signals = []
        for identifier in identifiers:
            signals = active_signals(self.repo, self.config, identifier, at)
            all_signals.extend(signals)
            if signals:
                report["matches_with_signals"] += 1
            # Do not replace a good historical snapshot with a blank on provider outage.
            if identifier in report["failed_matches"] and not articles:
                continue
            self.repo.save_snapshot(identifier, at, {"match_id": identifier, "snapshot_time": at.isoformat(), "signals": signals})
            report["matches_updated"] += 1
        report["events_created"] = self.repo.counts()["events"] - before["events"]
        report["signals_by_type"] = dict(Counter(s["type"] for s in all_signals))
        report["source_tier_distribution"] = dict(Counter(a.source_tier for a in articles.values()))
        report["multi_source_event_fraction"] = sum(s["source_count"] > 1 for s in all_signals) / len(all_signals) if all_signals else 0
        report["total_counts"] = self.repo.counts()
        self.repo.save_run(report, at)
        (self.config.root / "latest_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        log.info("News update: %s", json.dumps(report, ensure_ascii=False))
        return report
