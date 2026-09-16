import hashlib
import json
import logging
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd
from app.config import DATA, OUTCOMES
from app.services.teams import normalize_team, team_id

COLUMNS = {
    "FTHG": "full_time_home_goals", "FTAG": "full_time_away_goals", "FTR": "full_time_result",
    "HTHG": "half_time_home_goals", "HTAG": "half_time_away_goals", "HTR": "half_time_result",
    "HS": "home_shots", "AS": "away_shots", "HST": "home_shots_on_target", "AST": "away_shots_on_target",
    "HC": "home_corners", "AC": "away_corners", "HY": "home_yellow_cards", "AY": "away_yellow_cards",
    "HR": "home_red_cards", "AR": "away_red_cards",
}
# Never silently substitute closing prices for pre-closing prices.
OPENING_ODDS = [("AvgH", "AvgD", "AvgA"), ("BbAvH", "BbAvD", "BbAvA"),
                ("B365H", "B365D", "B365A"), ("PSH", "PSD", "PSA")]
CLOSING_ODDS = [("AvgCH", "AvgCD", "AvgCA"), ("B365CH", "B365CD", "B365CA")]


def normalize_frame(raw: pd.DataFrame, season: str, league: str, source: str = "",
                    recorded_at: str = "") -> pd.DataFrame:
    frame = pd.DataFrame(index=raw.index)
    frame["date"] = pd.to_datetime(raw["Date"], dayfirst=True, format="mixed", errors="coerce").dt.normalize()
    frame["season"], frame["league"] = season, league
    for side in ("home", "away"):
        frame[f"{side}_team"] = raw[f"{side.title()}Team"].fillna("").map(normalize_team)
        frame[f"{side}_team_id"] = frame[f"{side}_team"].map(team_id)
    for original, column in COLUMNS.items():
        values = raw[original] if original in raw else pd.Series(np.nan, index=raw.index)
        frame[column] = values if original in ("FTR", "HTR") else pd.to_numeric(values, errors="coerce")
    # Keep all detected 1X2 source columns for audit, even when not used by v1.
    for column in raw.columns:
        if re.fullmatch(r"(?:Avg|Max|BbAv|BbMx|B365|BW|IW|LB|PS|WH|SJ|VC|GB|BS|BF|BFE)C?[HDA]", column):
            frame[f"odds_raw_{column}"] = pd.to_numeric(raw[column], errors="coerce")
    for prefix, candidates in (("market", OPENING_ODDS), ("closing", CLOSING_ODDS)):
        selected = pd.DataFrame(np.nan, index=raw.index, columns=list(OUTCOMES))
        source_names = pd.Series(None, index=raw.index, dtype=object)
        for columns in candidates:
            if not set(columns).issubset(raw.columns):
                continue
            odds = raw[list(columns)].apply(pd.to_numeric, errors="coerce")
            odds.columns = list(OUTCOMES)
            valid = (odds > 1).all(axis=1) & np.isfinite(odds).all(axis=1) & selected.isna().all(axis=1)
            selected.loc[valid] = odds.loc[valid]
            source_names.loc[valid] = "/".join(columns)
        inverse = 1 / selected
        probabilities = inverse.div(inverse.sum(axis=1), axis=0)
        for outcome in OUTCOMES:
            frame[f"{prefix}_odds_{outcome}"] = selected[outcome]
            frame[f"{prefix}_prob_{outcome}"] = probabilities[outcome]
        frame[f"{prefix}_odds_source"] = source_names
    frame["source"], frame["recorded_at"] = source, recorded_at
    # Football-Data does not supply observation timestamps for these historical odds.
    frame["odds_valid_at"] = pd.NaT
    frame = frame[frame.date.notna() & frame.full_time_result.isin(["H", "D", "A"])
                  & frame.full_time_home_goals.notna() & frame.full_time_away_goals.notna()
                  & frame.home_team.ne("") & frame.away_team.ne("")].copy()
    frame["match_id"] = frame.apply(lambda row: hashlib.sha256(
        f"{row.date.date()}|{league}|{row.home_team_id}|{row.away_team_id}".encode()).hexdigest()[:24], axis=1)
    return frame


def normalize() -> dict:
    manifest_path = DATA / "raw" / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError("Dataset saknas. Kör scripts/download_football_data.py först.")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    frames, failures, inventories = [], [], {}
    for key, item in sorted(manifest.items()):
        try:
            path = DATA / "raw" / item["path"]
            if hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
                raise ValueError("Raw checksum mismatch")
            raw = pd.read_csv(path, encoding="utf-8-sig")
            frame = normalize_frame(raw, item["season"], item["league"], item["source"], item["recorded_at"])
            frames.append(frame)
            inventories[key] = {"raw_rows": len(raw), "completed_matches": len(frame),
                                "odds_columns": [c[9:] for c in frame if c.startswith("odds_raw_")]}
        except (OSError, ValueError, KeyError) as exc:
            failures.append({"file": key, "error": str(exc)})
            logging.warning("Normalization failed %s: %s", key, exc)
    if not frames:
        raise ValueError("Ingen giltig historisk data kunde normaliseras.")
    combined = pd.concat(frames, ignore_index=True).sort_values(["date", "match_id"]).drop_duplicates("match_id")
    destination = DATA / "processed"
    destination.mkdir(parents=True, exist_ok=True)
    combined.to_parquet(destination / "matches.parquet", index=False)
    report = {"total": len(combined), "leagues": combined.league.value_counts().to_dict(),
              "seasons": sorted(combined.season.unique().tolist()), "files": inventories, "failed": failures,
              "missing_market": int(combined.market_prob_home.isna().sum()),
              "first_date": str(combined.date.min().date()), "last_date": str(combined.date.max().date())}
    (destination / "normalization_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    report = normalize()
    print(json.dumps({k: v for k, v in report.items() if k != "files"}, indent=2))
