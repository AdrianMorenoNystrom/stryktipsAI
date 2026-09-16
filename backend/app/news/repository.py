"""SQLite stores immutable observations and snapshots. Raw provider bytes are content-addressed."""
from datetime import datetime
import json
from pathlib import Path
from app.storage import SQLiteArchive, now_utc
from app.news.entities import digest, player_alias_key, player_initial_key
from app.news.schemas import NewsArticle, PlayerEntity


class NewsRepository(SQLiteArchive):
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = root / "news.sqlite3"
        with self.connection() as con:
            con.executescript("""
                CREATE TABLE IF NOT EXISTS articles(id TEXT PRIMARY KEY, canonical_url TEXT UNIQUE NOT NULL);
                CREATE TABLE IF NOT EXISTS article_versions(id TEXT PRIMARY KEY, article_id TEXT NOT NULL, retrieved_at TEXT NOT NULL, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS match_articles(match_id TEXT NOT NULL, article_version_id TEXT NOT NULL, recorded_at TEXT NOT NULL, PRIMARY KEY(match_id, article_version_id));
                CREATE TABLE IF NOT EXISTS extractions(id TEXT PRIMARY KEY, article_version_id TEXT NOT NULL, extractor TEXT NOT NULL, payload TEXT NOT NULL, recorded_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS players(id TEXT PRIMARY KEY, team_id TEXT NOT NULL, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS player_aliases(team_id TEXT NOT NULL, alias TEXT NOT NULL, player_id TEXT NOT NULL, UNIQUE(team_id, alias, player_id));
                CREATE TABLE IF NOT EXISTS events(id TEXT PRIMARY KEY, match_id TEXT NOT NULL, team_id TEXT NOT NULL, entity_key TEXT NOT NULL, family TEXT NOT NULL, first_published_at TEXT NOT NULL, title TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS observations(id TEXT PRIMARY KEY, event_id TEXT NOT NULL, match_id TEXT NOT NULL, recorded_at TEXT NOT NULL, published_at TEXT NOT NULL, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS snapshots(id TEXT PRIMARY KEY, match_id TEXT NOT NULL, snapshot_time TEXT NOT NULL, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS coupon_snapshots(id TEXT PRIMARY KEY, coupon_id TEXT NOT NULL, recorded_at TEXT NOT NULL, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS query_cache(id TEXT PRIMARY KEY, created_at TEXT NOT NULL, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY, recorded_at TEXT NOT NULL, payload TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS observations_asof ON observations(match_id, recorded_at);
                CREATE INDEX IF NOT EXISTS snapshots_asof ON snapshots(match_id, snapshot_time);
            """)

    def save_article(self, article: NewsArticle) -> bool:
        with self.connection() as con:
            con.execute("INSERT OR IGNORE INTO articles VALUES (?, ?)", (article.id, str(article.url)))
            return bool(con.execute("INSERT OR IGNORE INTO article_versions VALUES (?, ?, ?, ?)",
                (article.version_id, article.id, article.retrieved_at.isoformat(), article.model_dump_json())).rowcount)

    def extraction(self, version: str, extractor: str) -> dict | None:
        with self.connection() as con:
            row = con.execute("SELECT payload FROM extractions WHERE id=?", (digest(version + extractor),)).fetchone()
            return json.loads(row[0]) if row else None

    def link_article(self, match_id: str, version_id: str, recorded: datetime) -> None:
        with self.connection() as con:
            con.execute("INSERT OR IGNORE INTO match_articles VALUES (?, ?, ?)", (match_id, version_id, recorded.isoformat()))

    def match_sources(self, match_id: str, as_of: datetime) -> list[dict]:
        with self.connection() as con:
            rows = con.execute("SELECT v.payload FROM match_articles m JOIN article_versions v ON m.article_version_id=v.id WHERE m.match_id=? AND m.recorded_at<=? AND v.retrieved_at<=? ORDER BY v.retrieved_at",
                               (match_id, as_of.isoformat(), as_of.isoformat())).fetchall()
            articles = {json.loads(row[0])["id"]: json.loads(row[0]) for row in rows}
            return list(articles.values())

    def save_extraction(self, version: str, extractor: str, payload: dict, recorded: datetime) -> None:
        with self.connection() as con:
            con.execute("INSERT OR IGNORE INTO extractions VALUES (?, ?, ?, ?, ?)",
                        (digest(version + extractor), version, extractor, json.dumps(payload), recorded.isoformat()))

    def player(self, name: str, team: str) -> PlayerEntity:
        alias, initial = player_alias_key(name), player_initial_key(name)
        with self.connection() as con:
            matches = con.execute("SELECT DISTINCT player_id FROM player_aliases WHERE team_id=? AND alias=?", (team, alias)).fetchall()
            if not matches and (len(name.split()[0].strip('.')) == 1):
                matches = con.execute("SELECT DISTINCT player_id FROM player_aliases WHERE team_id=? AND alias=?", (team, initial)).fetchall()
            if not matches:
                abbreviated = con.execute("SELECT p.payload FROM players p JOIN player_aliases a ON p.id=a.player_id WHERE a.team_id=? AND a.alias=?", (team, initial)).fetchall()
                candidates = [PlayerEntity.model_validate_json(row[0]) for row in abbreviated]
                candidates = [p for p in candidates if len(p.canonical_name.split()[0].strip('.')) == 1]
                if len(candidates) == 1:
                    entity = candidates[0].model_copy(update={"canonical_name": name, "aliases": sorted(set([*candidates[0].aliases, name]))})
                    con.execute("UPDATE players SET payload=? WHERE id=?", (entity.model_dump_json(), entity.player_id))
                    con.execute("INSERT OR IGNORE INTO player_aliases VALUES (?, ?, ?)", (team, alias, entity.player_id))
                    return entity
            if len(matches) == 1:
                return PlayerEntity.model_validate_json(con.execute("SELECT payload FROM players WHERE id=?", (matches[0][0],)).fetchone()[0])
            entity = PlayerEntity(player_id=digest(team + alias), canonical_name=name, team_id=team, aliases=[name])
            con.execute("INSERT OR IGNORE INTO players VALUES (?, ?, ?)", (entity.player_id, team, entity.model_dump_json()))
            for candidate in (alias, initial):
                con.execute("INSERT OR IGNORE INTO player_aliases VALUES (?, ?, ?)", (team, candidate, entity.player_id))
            return entity

    def observations(self, match_id: str, as_of: datetime) -> list[dict]:
        with self.connection() as con:
            rows = con.execute("SELECT payload FROM observations WHERE match_id=? AND recorded_at<=? AND published_at<=? ORDER BY published_at, id",
                               (match_id, as_of.isoformat(), as_of.isoformat())).fetchall()
            return [json.loads(row[0]) for row in rows]

    def article_sources(self, ids: list[str], as_of: datetime) -> list[dict]:
        if not ids:
            return []
        with self.connection() as con:
            rows = con.execute("SELECT payload FROM article_versions WHERE id IN (" + ",".join("?" for _ in ids) + ") AND retrieved_at<=?", [*ids, as_of.isoformat()]).fetchall()
            return [json.loads(row[0]) for row in rows]

    def save_snapshot(self, match_id: str, as_of: datetime, payload: dict) -> None:
        with self.connection() as con:
            con.execute("INSERT OR IGNORE INTO snapshots VALUES (?, ?, ?, ?)",
                        (digest(match_id + as_of.isoformat()), match_id, as_of.isoformat(), json.dumps(payload)))

    def snapshot(self, match_id: str, as_of: datetime) -> dict | None:
        with self.connection() as con:
            row = con.execute("SELECT payload FROM snapshots WHERE match_id=? AND snapshot_time<=? ORDER BY snapshot_time DESC LIMIT 1",
                              (match_id, as_of.isoformat())).fetchone()
            return json.loads(row[0]) if row else None

    def save_coupon(self, coupon: dict, recorded: datetime) -> None:
        payload = json.dumps(coupon, sort_keys=True, ensure_ascii=False)
        with self.connection() as con:
            latest = con.execute("SELECT payload FROM coupon_snapshots ORDER BY recorded_at DESC LIMIT 1").fetchone()
            if latest and latest[0] == payload:
                return
            con.execute("INSERT OR IGNORE INTO coupon_snapshots VALUES (?, ?, ?, ?)",
                        (digest(payload + recorded.isoformat()), coupon["id"], recorded.isoformat(), payload))

    def current_coupon(self) -> dict | None:
        with self.connection() as con:
            row = con.execute("SELECT payload FROM coupon_snapshots ORDER BY recorded_at DESC LIMIT 1").fetchone()
            return json.loads(row[0]) if row else None

    def coupon_history(self, coupon_id: str) -> list[dict]:
        with self.connection() as con:
            return [{"recorded_at": row[0], "coupon": json.loads(row[1])} for row in con.execute(
                "SELECT recorded_at, payload FROM coupon_snapshots WHERE coupon_id=? ORDER BY recorded_at", (coupon_id,))]

    def cache_get(self, key: str, cutoff: datetime) -> list[dict] | None:
        with self.connection() as con:
            row = con.execute("SELECT payload FROM query_cache WHERE id=? AND created_at>=?", (key, cutoff.isoformat())).fetchone()
            return json.loads(row[0]) if row else None

    def cache_put(self, key: str, created: datetime, payload: list[dict]) -> None:
        with self.connection() as con:
            con.execute("INSERT OR REPLACE INTO query_cache VALUES (?, ?, ?)", (key, created.isoformat(), json.dumps(payload)))

    def save_run(self, report: dict, time: datetime) -> None:
        with self.connection() as con:
            con.execute("INSERT OR IGNORE INTO runs VALUES (?, ?, ?)", (digest(time.isoformat()), time.isoformat(), json.dumps(report)))

    def latest_run(self) -> dict | None:
        with self.connection() as con:
            row = con.execute("SELECT payload FROM runs ORDER BY recorded_at DESC LIMIT 1").fetchone()
            return json.loads(row[0]) if row else None

    def counts(self) -> dict:
        with self.connection() as con:
            return {table: con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in ("articles", "article_versions", "events", "observations", "players", "snapshots", "extractions")}
