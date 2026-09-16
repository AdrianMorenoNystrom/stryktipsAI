"""Date-batched state updates: every feature is computed BEFORE that day's results.

The same state implementation is used for training and inference. No closing odds,
current-match statistics, or future observations are allowed into feature columns.
New external signals should join point-in-time rows before model fitting; they must
provide recorded_at <= prediction cutoff and valid_at, plus a new feature version.
"""
from collections import defaultdict, deque
from dataclasses import dataclass, field
import math

import numpy as np
import pandas as pd
from app.config import ELO_HOME_ADVANTAGE, ELO_INITIAL, ELO_K, OUTCOMES, ROLLING_WINDOWS

STATS = ("points", "goals_for", "goals_against", "shots", "sot")
FEATURE_VERSION = 1


@dataclass
class TeamState:
    elo: float = ELO_INITIAL
    total: int = 0
    history: deque = field(default_factory=lambda: deque(maxlen=max(ROLLING_WINDOWS)))
    home: deque = field(default_factory=lambda: deque(maxlen=max(ROLLING_WINDOWS)))
    away: deque = field(default_factory=lambda: deque(maxlen=max(ROLLING_WINDOWS)))
    last_date: pd.Timestamp | None = None
    season: str | None = None
    league: str | None = None


def mean_stat(history: deque, stat: str, window: int) -> float:
    values = [r[stat] for r in list(history)[-window:] if math.isfinite(r[stat])]
    return float(np.mean(values)) if values else float("nan")


class FeatureState:
    def __init__(self, season_regression: float = 1.0, division_adjustment: float = 0.0) -> None:
        self.teams: dict[str, TeamState] = defaultdict(TeamState)
        self.season_regression = season_regression
        self.division_adjustment = division_adjustment

    def begin_day(self, rows: list[dict]) -> None:
        # League membership in the fixture is known pre-match; means use only past ratings.
        means = {league: float(np.mean([s.elo for s in self.teams.values() if s.league == league]))
                 for league in ("E0", "E1", "E2") if any(s.league == league for s in self.teams.values())}
        for row in rows:
            for side in ("home", "away"):
                state = self.teams[row[f"{side}_team_id"]]
                if state.season is not None and state.season != row["season"]:
                    mean = means.get(row["league"], ELO_INITIAL)
                    state.elo = mean + self.season_regression * (state.elo - mean)
                    if state.league is not None:
                        state.elo += self.division_adjustment * (int(row["league"][1]) - int(state.league[1]))
                state.season, state.league = row["season"], row["league"]

    def features(self, row: dict) -> dict:
        home = self.teams[row["home_team_id"]]
        away = self.teams[row["away_team_id"]]
        result = {"league": row["league"], "home_elo_before": home.elo, "away_elo_before": away.elo,
                  "elo_difference": home.elo + ELO_HOME_ADVANTAGE - away.elo}
        for outcome in OUTCOMES:
            result[f"market_prob_{outcome}"] = row.get(f"market_prob_{outcome}", np.nan)
        for side, state in (("home", home), ("away", away)):
            result[f"days_since_last_match_{side}"] = (
                (pd.Timestamp(row["date"]).normalize() - state.last_date).days if state.last_date is not None else np.nan)
            for window in ROLLING_WINDOWS:
                for stat in STATS:
                    result[f"{side}_{stat}_avg_{window}"] = mean_stat(state.history, stat, window)
                    result[f"{side}_venue_{stat}_avg_{window}"] = mean_stat(getattr(state, side), stat, window)
        result["rest_difference"] = result["days_since_last_match_home"] - result["days_since_last_match_away"]
        return result

    def update(self, row: dict) -> None:
        home, away = self.teams[row["home_team_id"]], self.teams[row["away_team_id"]]
        expected = 1 / (1 + 10 ** ((away.elo - home.elo - ELO_HOME_ADVANTAGE) / 400))
        actual = {"H": 1.0, "D": 0.5, "A": 0.0}[row["full_time_result"]]
        change = ELO_K * (actual - expected)
        home.elo += change
        away.elo -= change
        for side, other, state, score in (("home", "away", home, actual), ("away", "home", away, 1 - actual)):
            stats = {"date": str(pd.Timestamp(row["date"]).date()),
                     "opponent": row[f"{other}_team"], "venue": side,
                     "points": 3.0 if score == 1 else 1.0 if score == 0.5 else 0.0,
                     "goals_for": float(row[f"full_time_{side}_goals"]),
                     "goals_against": float(row[f"full_time_{other}_goals"]),
                     "shots": float(row.get(f"{side}_shots", np.nan)),
                     "sot": float(row.get(f"{side}_shots_on_target", np.nan))}
            state.history.append(stats)
            getattr(state, side).append(stats)
            state.last_date = pd.Timestamp(row["date"]).normalize()
            state.total += 1


def build_features(matches: pd.DataFrame, season_regression: float = 1.0,
                   division_adjustment: float = 0.0) -> tuple[pd.DataFrame, FeatureState]:
    state = FeatureState(season_regression, division_adjustment)
    output = []
    for _, day in matches.sort_values(["date", "match_id"]).groupby("date", sort=True):
        rows = day.to_dict("records")
        state.begin_day(rows)
        for row in rows:
            output.append({**state.features(row), "match_id": row["match_id"], "date": row["date"],
                           "season": row["season"], "target": {"H": 0, "D": 1, "A": 2}[row["full_time_result"]]})
        for row in rows:
            state.update(row)
    return pd.DataFrame(output), state
