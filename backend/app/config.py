"""Shared configuration; browser receives product settings from /api/config."""
import os
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(os.environ.get("STRYKTIPS_DATA_DIR", ROOT / "data" / "football_data"))
ARTIFACTS = Path(os.environ.get("STRYKTIPS_ARTIFACT_DIR", ROOT / "artifacts"))
LEAGUES = {"E0": "Premier League", "E1": "Championship", "E2": "League One"}
START_SEASON = 2010
SEED = 42
REGULARIZATION_CANDIDATES = (0.01, 0.1, 1.0)
MAX_TRAIN_ITERATIONS = 2500
ELO_INITIAL = 1500.0
ELO_HOME_ADVANTAGE = 65.0
ELO_K = 20.0
ROLLING_WINDOWS = (5, 10)
MIN_HISTORY = 5
CROWD_TOLERANCE = 1.0
VALUE_FLOOR = 0.005
ROW_COST = float(os.environ.get("STRYKTIPS_ROW_COST", "1"))
if not 0 < ROW_COST < 1000:
    raise ValueError("STRYKTIPS_ROW_COST must be between 0 and 1000")
BUDGET_PRESETS = [64, 128, 256, 512]
# probability coverage, weighted edge, log value, guarding cost
OPTIMIZER_WEIGHTS = {
    "optimal": (1.0, 0.65, 0.30, 0.04),
    "safe": (1.4, 0.10, 0.04, 0.04),
    "value": (0.8, 1.20, 0.70, 0.04),
}
OUTCOMES = ("home", "draw", "away")
SIGNS = ("1", "X", "2")


def current_season(today: date | None = None) -> int:
    today = today or date.today()
    return today.year if today.month >= 7 else today.year - 1


def season_label(year: int) -> str:
    return f"{year}-{str(year + 1)[-2:]}"
