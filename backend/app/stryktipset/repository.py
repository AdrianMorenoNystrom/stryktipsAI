"""Append-only source observations; current indexes never replace historical evidence."""
from datetime import datetime
import hashlib
import json
from pathlib import Path
from uuid import uuid4
from app.storage import SQLiteArchive, iso, now_utc
from app.database import PersistentArchive
from app.stryktipset.schemas import Draw, DrawResult
from app.services.probabilities import devig


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:32]


def encode(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def fixture_key(match) -> str:
    return digest(str(match.provider_event_id) + '|' + match.source_home_team + '|' + match.source_away_team)


class DrawRepository(PersistentArchive):
    def __init__(self, root: Path) -> None:
        self.root = root
        root.mkdir(parents=True, exist_ok=True)
        self.path = root / "stryktipset.sqlite3"
        if self.database_url:
            return  # Production schema is changed only by versioned migrations.
        with self.connection() as con:
            con.executescript("""
              CREATE TABLE IF NOT EXISTS provider_raw_payloads(id TEXT PRIMARY KEY, source TEXT NOT NULL, retrieved_at TEXT NOT NULL, http_status INTEGER NOT NULL, raw_path TEXT NOT NULL);
              CREATE INDEX IF NOT EXISTS raw_source_time ON provider_raw_payloads(source,retrieved_at);
              CREATE TABLE IF NOT EXISTS provider_health(id TEXT PRIMARY KEY, at TEXT NOT NULL, successful INTEGER NOT NULL, source TEXT NOT NULL, issue TEXT);
              CREATE INDEX IF NOT EXISTS health_time ON provider_health(at);
              CREATE TABLE IF NOT EXISTS stryktipset_draws(draw_number INTEGER PRIMARY KEY, sales_close_at TEXT NOT NULL, status TEXT NOT NULL, retrieved_at TEXT NOT NULL, payload TEXT NOT NULL);
              CREATE INDEX IF NOT EXISTS draws_close ON stryktipset_draws(sales_close_at);
              CREATE TABLE IF NOT EXISTS stryktipset_matches(draw_number INTEGER NOT NULL, number INTEGER NOT NULL, match_id TEXT NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(draw_number,number));
              CREATE INDEX IF NOT EXISTS matches_id ON stryktipset_matches(match_id);
              CREATE TABLE IF NOT EXISTS draw_observations(id TEXT PRIMARY KEY, draw_number INTEGER NOT NULL, recorded_at TEXT NOT NULL, retrieved_at TEXT NOT NULL, raw_id TEXT NOT NULL, payload TEXT NOT NULL);
              CREATE INDEX IF NOT EXISTS draw_observation_time ON draw_observations(draw_number,recorded_at);
              CREATE TABLE IF NOT EXISTS crowd_snapshots(id TEXT PRIMARY KEY, observation_id TEXT NOT NULL, draw_number INTEGER NOT NULL, number INTEGER NOT NULL, match_id TEXT NOT NULL, recorded_at TEXT NOT NULL, retrieved_at TEXT NOT NULL, source_updated_at TEXT, is_pre_close_snapshot INTEGER NOT NULL, payload TEXT NOT NULL);
              CREATE INDEX IF NOT EXISTS crowd_time ON crowd_snapshots(draw_number,number,recorded_at);
              CREATE TABLE IF NOT EXISTS market_snapshots(id TEXT PRIMARY KEY, observation_id TEXT, draw_number INTEGER NOT NULL, number INTEGER NOT NULL, match_id TEXT NOT NULL, recorded_at TEXT NOT NULL, retrieved_at TEXT NOT NULL, source_updated_at TEXT, payload TEXT NOT NULL);
              CREATE INDEX IF NOT EXISTS market_time ON market_snapshots(draw_number,number,recorded_at);
              CREATE TABLE IF NOT EXISTS prediction_snapshots(id TEXT PRIMARY KEY, run_id TEXT NOT NULL, draw_number INTEGER NOT NULL, number INTEGER NOT NULL, match_id TEXT NOT NULL, predicted_at TEXT NOT NULL, payload TEXT NOT NULL);
              CREATE INDEX IF NOT EXISTS predictions_time ON prediction_snapshots(draw_number,number,predicted_at);
              CREATE TABLE IF NOT EXISTS optimizer_snapshots(id TEXT PRIMARY KEY, draw_number INTEGER NOT NULL, created_at TEXT NOT NULL, budget REAL NOT NULL, profile TEXT NOT NULL, payload TEXT NOT NULL);
              CREATE INDEX IF NOT EXISTS optimizer_time ON optimizer_snapshots(draw_number,created_at);
              CREATE TABLE IF NOT EXISTS result_observations(id TEXT PRIMARY KEY, draw_number INTEGER NOT NULL, recorded_at TEXT NOT NULL, raw_id TEXT NOT NULL, completed INTEGER NOT NULL, payload TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS match_results(result_id TEXT NOT NULL, draw_number INTEGER NOT NULL, number INTEGER NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(result_id,number));
              CREATE TABLE IF NOT EXISTS draw_payouts(result_id TEXT NOT NULL, draw_number INTEGER NOT NULL, correct INTEGER NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(result_id,correct));
              CREATE INDEX IF NOT EXISTS results_draw ON result_observations(draw_number,recorded_at);
            """)
            con.executescript((Path(__file__).resolve().parents[2] / 'migrations' / '002_market_collection.sql').read_text(encoding='utf-8').replace('TIMESTAMPTZ', 'TEXT').replace('BYTEA', 'BLOB'))

    def archive(self, source: str, status: int, raw: bytes, retrieved_at: datetime) -> dict:
        path = self.save_raw(raw)
        identifier = digest(source + iso(retrieved_at) + path)
        record = {"id":identifier, "source":source, "http_status":status, "raw_path":path, "retrieved_at":iso(retrieved_at)}
        with self.connection() as con:
            con.execute("INSERT OR IGNORE INTO provider_raw_payloads VALUES (?,?,?,?,?)", (identifier,source,iso(retrieved_at),status,path))
        return record

    def cached_raw(self, source: str, cutoff: datetime | None = None) -> dict | None:
        with self.connection() as con:
            row = con.execute("SELECT * FROM provider_raw_payloads WHERE source=? AND http_status=200" + (" AND retrieved_at>=?" if cutoff else "") + " ORDER BY retrieved_at DESC LIMIT 1", (source,iso(cutoff)) if cutoff else (source,)).fetchone()
            return dict(row) if row else None

    def record_health(self, successful: bool, source: str, issue: str | None, at: datetime) -> None:
        with self.connection() as con:
            con.execute("INSERT OR IGNORE INTO provider_health VALUES (?,?,?,?,?)", (digest(source+iso(at)+str(successful)),iso(at),int(successful),source,issue))

    def health(self, source: str | None = None) -> dict:
        with self.connection() as con:
            latest = con.execute("SELECT * FROM provider_health" + (" WHERE source=?" if source else "") + " ORDER BY at DESC LIMIT 1", (source,) if source else ()).fetchone()
            success = con.execute("SELECT MAX(at) FROM provider_health WHERE successful=1" + (" AND source=?" if source else ""), (source,) if source else ()).fetchone()[0]
        return {"provider":"svenska-spel", "status":"Healthy" if latest and latest['successful'] else "Degraded" if success else "Unavailable",
                "last_successful_fetch":success, "last_attempt":latest['at'] if latest else None,
                "issue":latest['issue'] if latest and not latest['successful'] else None}

    def save_draw(self, draw: Draw, recorded_at: datetime) -> str:
        if recorded_at < draw.retrieved_at:
            raise ValueError("Cannot record a future retrieval")
        observation = digest(draw.raw_id + str(draw.draw_number))
        payload = draw.model_dump(mode="json")
        at, retrieved = iso(recorded_at), iso(draw.retrieved_at)
        with self.connection() as con:
            existing = con.execute("SELECT retrieved_at FROM stryktipset_draws WHERE draw_number=?",(draw.draw_number,)).fetchone()
            is_latest = not existing or retrieved >= existing[0]
            inserted = con.execute("INSERT OR IGNORE INTO draw_observations VALUES (?,?,?,?,?,?)", (observation,draw.draw_number,at,retrieved,draw.raw_id,encode(payload))).rowcount
            if not inserted:
                return observation
            con.execute("INSERT INTO stryktipset_draws VALUES (?,?,?,?,?) ON CONFLICT(draw_number) DO UPDATE SET sales_close_at=excluded.sales_close_at,status=excluded.status,retrieved_at=excluded.retrieved_at,payload=excluded.payload WHERE excluded.retrieved_at>=stryktipset_draws.retrieved_at", (draw.draw_number,iso(draw.sales_close_at),draw.status,retrieved,encode(payload)))
            for match in draw.matches:
                if is_latest:
                    con.execute("INSERT INTO stryktipset_matches VALUES (?,?,?,?) ON CONFLICT(draw_number,number) DO UPDATE SET payload=excluded.payload,match_id=excluded.match_id", (draw.draw_number,match.number,match.match_id,match.model_dump_json()))
                if match.crowd:
                    source_time = match.crowd_source_updated_at
                    pre_close = recorded_at < draw.sales_close_at and draw.retrieved_at < draw.sales_close_at and (source_time is None or source_time < draw.sales_close_at)
                    identifier = digest(observation + ':crowd:' + str(match.number))
                    crowd = {"id":identifier,"draw_number":draw.draw_number,"number":match.number,"match_id":match.match_id,
                        "recorded_at":at,"retrieved_at":retrieved,"source_updated_at":iso(source_time) if source_time else None,
                        "crowd":match.crowd.model_dump(),"provider":draw.provider,"source":draw.source,"raw_id":draw.raw_id,
                        "is_pre_close_snapshot":pre_close,"observation_id":observation,"fixture_key":fixture_key(match)}
                    con.execute("INSERT INTO crowd_snapshots VALUES (?,?,?,?,?,?,?,?,?,?)", (identifier,observation,draw.draw_number,match.number,match.match_id,at,retrieved,iso(source_time) if source_time else None,int(pre_close),encode(crowd)))
                if match.market_odds:
                    self._market(con, draw.draw_number, match.number, match.match_id, match.market_odds.model_dump(), draw.source + "#drawEvents.odds", recorded_at, draw.retrieved_at, observation,fixture_key(match))
        return observation

    def _market(self, con, draw_number, number, match_id, odds, source, recorded_at, retrieved_at, observation=None,fixture=None):
        identifier = digest(f"{observation}:{draw_number}:{number}:{iso(recorded_at)}:{source}:{encode(odds)}")
        payload = {"id":identifier,"draw_number":draw_number,"number":number,"match_id":match_id,"odds":odds,
            "market":devig(odds),"recorded_at":iso(recorded_at),"retrieved_at":iso(retrieved_at),"source_updated_at":None,
            "source":source,"provider":"manual" if source == "manual" else "svenska-spel","observation_id":observation,"fixture_key":fixture}
        con.execute("INSERT OR IGNORE INTO market_snapshots VALUES (?,?,?,?,?,?,?,?,?)", (identifier,observation,draw_number,number,match_id,iso(recorded_at),iso(retrieved_at),None,encode(payload)))

    def save_manual_odds(self, draw: Draw, odds: dict[int, dict], at: datetime) -> None:
        with self.connection() as con:
            for match in draw.matches:
                if match.number in odds:
                    self._market(con,draw.draw_number,match.number,match.match_id,odds[match.number],"manual",at,at,fixture=fixture_key(match))

    def draw(self, draw_number: int) -> Draw | None:
        with self.connection() as con:
            row = con.execute("SELECT payload FROM stryktipset_draws WHERE draw_number=?", (draw_number,)).fetchone()
            return Draw.model_validate_json(row[0]) if row else None

    def draws(self) -> list[Draw]:
        with self.connection() as con:
            return [Draw.model_validate_json(row[0]) for row in con.execute("SELECT payload FROM stryktipset_draws ORDER BY sales_close_at DESC")]

    def observations(self, draw_number: int) -> list[dict]:
        with self.connection() as con:
            return [{**dict(row),"draw":json.loads(row['payload'])} for row in con.execute("SELECT id,draw_number,recorded_at,retrieved_at,raw_id,payload FROM draw_observations WHERE draw_number=? ORDER BY recorded_at", (draw_number,))]

    def observation_asof(self, draw_number: int, at: datetime) -> dict | None:
        with self.connection() as con:
            row = con.execute("SELECT * FROM draw_observations WHERE draw_number=? AND recorded_at<=? AND retrieved_at<=? ORDER BY retrieved_at DESC,recorded_at DESC LIMIT 1", (draw_number,iso(at),iso(at))).fetchone()
            return {**dict(row),"draw":json.loads(row['payload'])} if row else None

    def inputs_asof(self, draw_number: int, at: datetime) -> tuple[dict, dict]:
        output = []
        with self.connection() as con:
            for table in ("crowd_snapshots", "market_snapshots"):
                rows = con.execute(f"SELECT number,payload FROM {table} WHERE draw_number=? AND recorded_at<=? AND retrieved_at<=? AND (source_updated_at IS NULL OR source_updated_at<=?) ORDER BY retrieved_at,recorded_at,id", (draw_number,iso(at),iso(at),iso(at)))
                output.append({row[0]:json.loads(row[1]) for row in rows})
        return tuple(output)

    def crowd_history(self, draw_number: int, number: int, at: datetime) -> list[dict]:
        with self.connection() as con:
            return [json.loads(row[0]) for row in con.execute("SELECT payload FROM crowd_snapshots WHERE draw_number=? AND number=? AND recorded_at<=? AND retrieved_at<=? AND (source_updated_at IS NULL OR source_updated_at<=?) ORDER BY retrieved_at,recorded_at,id", (draw_number,number,iso(at),iso(at),iso(at)))]

    def pre_close(self, draw_number: int) -> dict | None:
        draw = self.draw(draw_number)
        if not draw:
            return None
        with self.connection() as con:
            # Require a complete, genuinely observed pre-close batch; no historical backdating.
            row = con.execute("SELECT observation_id,MAX(recorded_at) AS at FROM crowd_snapshots WHERE draw_number=? AND is_pre_close_snapshot=1 AND recorded_at<? AND retrieved_at<? AND (source_updated_at IS NULL OR source_updated_at<?) GROUP BY observation_id HAVING COUNT(DISTINCT number)=13 ORDER BY MAX(retrieved_at) DESC,at DESC LIMIT 1", (draw_number,iso(draw.sales_close_at),iso(draw.sales_close_at),iso(draw.sales_close_at))).fetchone()
            return dict(row) if row else None

    def save_analysis(self, draw: Draw, analysis: dict, inputs: dict, at: datetime, model: dict) -> dict:
        identifier = uuid4().hex
        system = analysis['system']
        previous = self.latest_system(draw.draw_number,at,system['budget'],system['mode'])
        changes = [{"number":i+1,"previous":old,"current":new} for i,(old,new) in enumerate(zip(previous['analysis']['system']['selections'],system['selections'])) if old != new] if previous else []
        record = {"id":identifier,"draw_number":draw.draw_number,"created_at":iso(at),"model":model,"inputs":inputs,"analysis":analysis,"changes":changes,
                  "is_pre_close":at < draw.sales_close_at}
        with self.connection() as con:
            for match in analysis['matches']:
                item = {"id":digest(identifier+str(match['number'])),"run_id":identifier,"draw_number":draw.draw_number,"predicted_at":iso(at),"model_metadata":model,"match":match,"inputs":inputs[str(match['number'])]}
                con.execute("INSERT INTO prediction_snapshots VALUES (?,?,?,?,?,?,?)", (item['id'],identifier,draw.draw_number,match['number'],f"ss:{draw.draw_number}:{match['number']}",iso(at),encode(item)))
            con.execute("INSERT INTO optimizer_snapshots VALUES (?,?,?,?,?,?)", (identifier,draw.draw_number,iso(at),system['budget'],system['mode'],encode(record)))
        return record

    def latest_system(self, draw_number: int, at: datetime, budget=None, profile=None) -> dict | None:
        with self.connection() as con:
            query = "SELECT payload FROM optimizer_snapshots WHERE draw_number=? AND created_at<=?"
            args = [draw_number,iso(at)]
            if budget is not None:
                query += " AND budget=? AND profile=?"
                args += [budget,profile]
            row = con.execute(query + " ORDER BY created_at DESC LIMIT 1",args).fetchone()
            return json.loads(row[0]) if row else None

    def systems(self, draw_number: int) -> list[dict]:
        with self.connection() as con:
            return [json.loads(row[0]) for row in con.execute("SELECT payload FROM optimizer_snapshots WHERE draw_number=? ORDER BY created_at",(draw_number,))]

    def save_result(self, result: DrawResult, at: datetime) -> None:
        identifier = digest(result.raw_id+':result:'+str(result.draw_number))
        with self.connection() as con:
            con.execute("INSERT OR IGNORE INTO result_observations VALUES (?,?,?,?,?,?)", (identifier,result.draw_number,iso(at),result.raw_id,int(result.completed),result.model_dump_json()))
            for match in result.matches:
                con.execute("INSERT OR IGNORE INTO match_results VALUES (?,?,?,?)",(identifier,result.draw_number,match.number,match.model_dump_json()))
            for payout in result.payouts:
                con.execute("INSERT OR IGNORE INTO draw_payouts VALUES (?,?,?,?)",(identifier,result.draw_number,payout.correct,payout.model_dump_json()))

    def result(self, draw_number: int) -> dict | None:
        with self.connection() as con:
            row = con.execute("SELECT payload,recorded_at FROM result_observations WHERE draw_number=? ORDER BY recorded_at DESC LIMIT 1",(draw_number,)).fetchone()
            return {**json.loads(row[0]),"recorded_at":row[1]} if row else None

    def counts(self) -> dict:
        with self.connection() as con:
            return {table:con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in ("stryktipset_draws","stryktipset_matches","draw_observations","crowd_snapshots","market_snapshots","prediction_snapshots","optimizer_snapshots","result_observations","match_results","draw_payouts","provider_raw_payloads")}
