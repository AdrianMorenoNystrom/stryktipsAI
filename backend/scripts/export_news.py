import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pandas as pd
from app.news.config import NewsConfig
from app.news.repository import NewsRepository, now_utc


def export_news() -> dict:
    config = NewsConfig()
    repo = NewsRepository(config.root)
    cutoff = now_utc()
    with repo.connection() as con:
        observations = [json.loads(row[0]) for row in con.execute("SELECT payload FROM observations WHERE recorded_at<=? ORDER BY recorded_at, id", (cutoff.isoformat(),))]
        snapshots = [{"match_id": row[0], "snapshot_time": row[1], "payload_json": row[2]} for row in con.execute("SELECT match_id,snapshot_time,payload FROM snapshots WHERE snapshot_time<=? ORDER BY snapshot_time", (cutoff.isoformat(),))]
    columns = ["id", "event_id", "match_id", "team_id", "type", "player_id", "direction", "certainty", "source_quality", "match_relevance", "first_published_at", "recorded_at", "article_version_id", "extractor"]
    destination = config.root / "processed"
    destination.mkdir(exist_ok=True)
    pd.DataFrame(observations, columns=columns).rename(columns={"type": "signal_type"}).to_parquet(destination / "news_signals.parquet", index=False)
    pd.DataFrame(snapshots, columns=["match_id", "snapshot_time", "payload_json"]).to_parquet(destination / "news_snapshots.parquet", index=False)
    return {"signals": len(observations), "snapshots": len(snapshots), "destination": str(destination), "outcomes_joined": False}


if __name__ == "__main__":
    print(json.dumps(export_news(), indent=2))
