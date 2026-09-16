"""Predeclared experiments and deployment gates; final audit season is not used for selection."""
FIRST_TEST_SEASON = 2020
RESIDUAL_PENALTIES = (0.01, 0.1, 1.0)
CALIBRATION_BIN_COUNT = 20
MIN_LOG_LOSS_GAIN = 0.0005
MIN_WINNING_SEASON_FRACTION = 0.6
MAX_ECE_REGRESSION = 0.002
VARIANTS = {
    "elo": {"groups": ["elo"]},
    "form": {"groups": ["elo", "form"]},
    "venue": {"groups": ["elo", "form", "venue"]},
    "full": {"groups": ["elo", "form", "venue", "rest"]},
    "league_interactions": {"groups": ["elo", "form", "venue", "rest"], "interactions": True},
    "season_085": {"groups": ["elo", "form", "venue", "rest"], "regression": 0.85},
    "season_065": {"groups": ["elo", "form", "venue", "rest"], "regression": 0.65},
    "promotion_75": {"groups": ["elo", "form", "venue", "rest"], "regression": 0.85, "division_adjustment": 75.0},
    "temperature": {"groups": ["elo", "form", "venue", "rest"], "calibrate": True},
}
MARKET_COLUMNS = ["market_prob_home", "market_prob_draw", "market_prob_away"]


def feature_columns(all_columns: list[str], groups: list[str]) -> list[str]:
    selected = []
    for column in all_columns:
        group = ("elo" if "elo" in column else "rest" if column.startswith("days_since") or column == "rest_difference"
                 else "venue" if "_venue_" in column else "form" if "_avg_" in column else None)
        if group in groups:
            selected.append(column)
    return selected
