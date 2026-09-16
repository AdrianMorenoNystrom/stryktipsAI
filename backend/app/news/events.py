"""Story grouping, transparent confidence, and as-of state from append-only evidence."""
from collections import defaultdict
from datetime import datetime
from difflib import SequenceMatcher
import json
import math
from app.news.config import NewsConfig, SOURCE_QUALITY
from app.news.entities import digest, normalized_title
from app.news.repository import NewsRepository
from app.news.schemas import ExtractedSignal, NewsArticle
from app.services.teams import team_id


def signal_family(kind: str) -> str:
    if kind in ("PLAYER_OUT", "PLAYER_DOUBTFUL", "PLAYER_RETURN", "PLAYER_SUSPENDED", "EXPECTED_STARTER_OUT", "FITNESS_LIMITATION"):
        return "availability"
    if "ROTATION" in kind or kind == "EXPECTED_LINEUP_CHANGE":
        return "lineup"
    return kind


def record_signal(repo: NewsRepository, config: NewsConfig, article: NewsArticle, signal: ExtractedSignal,
                  match_id: str, recorded: datetime, extractor: str) -> bool:
    team = team_id(signal.team)
    player = repo.player(signal.player, team) if signal.player else None
    family = signal_family(signal.type.value)
    entity_key = player.player_id if player else "team"
    title = normalized_title(signal.summary)
    with repo.connection() as con:
        candidates = con.execute("SELECT * FROM events WHERE match_id=? AND team_id=? AND entity_key=? AND family=?",
                                 (match_id, team, entity_key, family)).fetchall()
        event_id = None
        for candidate in candidates:
            age = abs((article.published_at - datetime.fromisoformat(candidate["first_published_at"])).total_seconds()) / 3600
            if player or (age <= config.story_hours and SequenceMatcher(None, title, candidate["title"]).ratio() >= config.story_similarity):
                event_id = candidate["id"]
                break
        event_id = event_id or digest("|".join([match_id, team, entity_key, family, "" if player else title]))
        con.execute("INSERT OR IGNORE INTO events VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (event_id, match_id, team, entity_key, family, article.published_at.isoformat(), title))
        identifier = digest(event_id + article.version_id + extractor + signal.type.value)
        payload = {"id": identifier, "event_id": event_id, "match_id": match_id, "team_id": team, "team": signal.team,
                   "player_id": player.player_id if player else None, "player": player.canonical_name if player else None,
                   **signal.model_dump(mode="json"), "article_id": article.id, "article_version_id": article.version_id,
                   "publisher": article.publisher, "source_tier": article.source_tier, "source_quality": SOURCE_QUALITY[article.source_tier],
                   "content_hash": article.content_hash, "first_published_at": article.published_at.isoformat(),
                   "recorded_at": recorded.isoformat(), "extractor": extractor,
                   "match_relevance": 1.0 if (recorded - article.published_at).total_seconds() < 86400 else .8 if (recorded - article.published_at).total_seconds() < 259200 else .5}
        return bool(con.execute("INSERT OR IGNORE INTO observations VALUES (?, ?, ?, ?, ?, ?)",
            (identifier, event_id, match_id, recorded.isoformat(), article.published_at.isoformat(), json.dumps(payload))).rowcount)


def active_signals(repo: NewsRepository, config: NewsConfig, match_id: str, as_of: datetime) -> list[dict]:
    groups = defaultdict(list)
    for observation in repo.observations(match_id, as_of):
        if (as_of - datetime.fromisoformat(observation["first_published_at"])).total_seconds() <= config.lookback_days * 86400:
            groups[observation["event_id"]].append(observation)
    signals = []
    for event_id, observations in groups.items():
        official = [o for o in observations if o["source_tier"] == 1]
        # A newer official observation supersedes the earlier claim; rumours cannot downgrade it.
        chosen = max(official or observations, key=lambda o: (o["first_published_at"], o["recorded_at"], o["id"]))
        supporting = [o for o in observations if o["type"] == chosen["type"]]
        publishers = {o["publisher"] for o in supporting}
        # Identical syndicated text never counts as independent confirmation.
        independent = min(len(publishers), len({o["content_hash"] for o in supporting}))
        hours = max(0, (as_of - datetime.fromisoformat(chosen["first_published_at"])).total_seconds() / 3600)
        recency = math.exp(-hours / 72)
        support = min(independent, 3) / 3
        confidence = .4 * chosen["source_quality"] + .25 * chosen["certainty"] + .2 * recency + .15 * support
        is_confirmed = chosen["source_tier"] == 1 and chosen["status"] == "confirmed"
        status = "Bekräftad" if is_confirmed else "Starkt rapporterad" if confidence >= config.strong_confidence and independent >= 2 else "Osäker uppgift" if confidence < config.uncertain_confidence else "Rapporterad"
        relevance = 1.0 if hours < 24 else .8 if hours < 72 else .5
        signals.append({**chosen, "id": event_id, "observation_id": chosen["id"], "confidence": confidence,
                        "status_label": status, "match_relevance": relevance, "source_count": len(publishers),
                        "independent_source_count": independent, "article_count": len({o["article_id"] for o in supporting}),
                        "source_article_ids": sorted({o["article_version_id"] for o in supporting}),
                        "first_published_at": min(o["first_published_at"] for o in observations),
                        "last_confirmed_at": max(o["first_published_at"] for o in supporting),
                        "has_conflicting_reports": any(o["type"] != chosen["type"] for o in observations),
                        "confidence_components": {"source_quality": chosen["source_quality"], "extraction_certainty": chosen["certainty"], "recency": recency, "independent_support": support}})
    return sorted(signals, key=lambda s: (-s["confidence"], s["id"]))
