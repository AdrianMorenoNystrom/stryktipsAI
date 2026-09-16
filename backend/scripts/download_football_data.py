"""Download immutable originals. New source versions get separate snapshot files."""
import argparse
import hashlib
import io
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import httpx
import pandas as pd
from app.config import DATA, LEAGUES, START_SEASON, current_season, season_label

log = logging.getLogger(__name__)


def download(start: int = START_SEASON, end: int | None = None,
             leagues: tuple[str, ...] = tuple(LEAGUES), refresh: bool = False) -> dict:
    end = current_season() if end is None else end
    if start > end or not set(leagues).issubset(LEAGUES):
        raise ValueError("Invalid seasons or leagues")
    raw = DATA / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    manifest_path = raw / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    report: dict = {"downloaded": [], "cached": [], "failed": []}
    transport = httpx.HTTPTransport(retries=3)
    with httpx.Client(transport=transport, timeout=45, follow_redirects=True) as client:
        for year in range(start, end + 1):
            for league in leagues:
                entry_key = f"{season_label(year)}/{league}"
                previous = manifest.get(entry_key)
                now = datetime.now(timezone.utc)
                if previous and (raw / previous["path"]).exists() and not refresh:
                    age = (now - datetime.fromisoformat(previous["recorded_at"])).total_seconds()
                    if year < current_season() and previous["recorded_at"][:10] >= f"{year + 1}-06-15" or age < 86400:
                        report["cached"].append(entry_key)
                        log.info("Cached %s", entry_key)
                        continue
                code = f"{year % 100:02d}{(year + 1) % 100:02d}"
                url = f"https://football-data.co.uk/mmz4281/{code}/{league}.csv"
                try:
                    for attempt in range(3):
                        response = client.get(url)
                        if response.status_code not in (429, 500, 502, 503, 504):
                            break
                        if attempt < 2:
                            time.sleep(0.5 * 2 ** attempt)
                    response.raise_for_status()
                    frame = pd.read_csv(io.BytesIO(response.content), encoding="utf-8-sig")
                    if not {"Date", "HomeTeam", "AwayTeam", "FTR"}.issubset(frame.columns) or frame.empty:
                        raise ValueError("Source did not contain a match CSV")
                    digest = hashlib.sha256(response.content).hexdigest()
                    folder = raw / season_label(year)
                    folder.mkdir(exist_ok=True)
                    original = folder / f"{league}.csv"
                    target = original if not original.exists() else folder / f"{league}.{digest[:16]}.csv"
                    if previous and previous["sha256"] == digest:
                        target = raw / previous["path"]
                    if not target.exists():
                        target.write_bytes(response.content)
                    manifest[entry_key] = {"path": target.relative_to(raw).as_posix(), "sha256": digest,
                                           "recorded_at": now.isoformat(), "source": url,
                                           "season": season_label(year), "league": league}
                    report["downloaded"].append(entry_key)
                    log.info("Downloaded %s (%d rows)", entry_key, len(frame))
                except (httpx.HTTPError, ValueError, UnicodeError, OSError) as exc:
                    report["failed"].append({"file": entry_key, "error": str(exc)})
                    log.warning("Failed %s: %s", entry_key, exc)
                # Commit progress after each file, so interruption is recoverable.
                temporary = manifest_path.with_suffix(".tmp")
                temporary.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
                temporary.replace(manifest_path)
    (DATA / "download_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=int, default=START_SEASON)
    parser.add_argument("--end", type=int, default=None)
    parser.add_argument("--leagues", nargs="+", choices=list(LEAGUES), default=list(LEAGUES))
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    result = download(args.start, args.end, tuple(args.leagues), args.refresh)
    print(json.dumps(result, indent=2))
    sys.exit(1 if not result["downloaded"] and not result["cached"] else 0)
