from itertools import product
import math
import pandas as pd
import pytest
from pydantic import ValidationError
from app.config import ELO_HOME_ADVANTAGE, ELO_INITIAL, ELO_K, OUTCOMES, ROW_COST
from app.demo import demo_coupon
from app.schemas import Coupon, Crowd, MatchInput
from app.services.objective import selection_score
from app.services.optimizer import SUBSETS, optimize, system_cost
from app.services.probabilities import devig, value_metrics
from app.services.teams import team_id
from ml.feature_engineering import build_features
from ml.predict import PredictionService
from scripts.normalize_football_data import normalize_frame


def history() -> pd.DataFrame:
    raw = pd.DataFrame({"Date": ["01/08/2020", "08/08/2020", "15/08/2020"],
                        "HomeTeam": ["Arsenal", "Everton", "Arsenal"], "AwayTeam": ["Everton", "Arsenal", "Everton"],
                        "FTHG": [2, 1, 3], "FTAG": [0, 1, 0], "FTR": ["H", "D", "H"],
                        "HS": [12, 8, 20], "AS": [6, 9, 5], "HST": [5, 2, 8], "AST": [1, 3, 0],
                        "AvgH": [1.8, 2.5, 1.7], "AvgD": [3.7, 3.2, 3.5], "AvgA": [4.8, 2.8, 5.0]})
    return normalize_frame(raw, "2020-21", "E0")


def test_devig_and_invalid_odds():
    probabilities = devig(dict(home=1.8, draw=3.7, away=4.8))
    assert sum(probabilities.values()) == pytest.approx(1)
    assert probabilities["home"] == pytest.approx((1 / 1.8) / (1 / 1.8 + 1 / 3.7 + 1 / 4.8))
    for bad in (0, 1, -1, float("nan"), float("inf")):
        with pytest.raises(ValueError):
            devig(dict(home=bad, draw=3.7, away=4.8))


def test_rolling_excludes_current_and_future_outcomes():
    data = history()
    original, _ = build_features(data)
    changed = data.copy()
    changed.loc[1:, "full_time_home_goals"] = 50
    changed.loc[1:, "full_time_result"] = "A"
    changed.loc[1:, "home_shots"] = 100
    altered, _ = build_features(changed)
    features = [c for c in original if c != "target"]
    pd.testing.assert_frame_equal(original.loc[:1, features], altered.loc[:1, features])
    assert math.isnan(original.iloc[0].home_points_avg_5)
    assert original.iloc[1].away_points_avg_5 == 3
    assert original.iloc[2].home_points_avg_5 == 2
    assert original.iloc[2].home_venue_points_avg_5 == 3
    assert original.iloc[2].home_goals_for_avg_5 == 1.5
    assert original.iloc[2].days_since_last_match_home == 7


def test_same_day_matches_cannot_see_each_others_results():
    data = history()
    data.loc[1, "date"] = data.loc[0, "date"]
    features, _ = build_features(data)
    assert (features.iloc[:2].home_elo_before == ELO_INITIAL).all()
    assert features.iloc[:2].home_points_avg_5.isna().all()


def test_elo_updates_only_after_result_and_is_zero_sum():
    features, state = build_features(history())
    expected_win = 1 / (1 + 10 ** (-ELO_HOME_ADVANTAGE / 400))
    delta = ELO_K * (1 - expected_win)
    assert features.iloc[0].home_elo_before == ELO_INITIAL
    assert features.iloc[1].away_elo_before == pytest.approx(ELO_INITIAL + delta)
    assert features.iloc[1].home_elo_before == pytest.approx(ELO_INITIAL - delta)
    assert sum(s.elo for s in state.teams.values()) == pytest.approx(2 * ELO_INITIAL)


def test_old_schema_nulls_and_no_closing_fallback():
    raw = pd.DataFrame({"Date": ["01/08/10"], "HomeTeam": ["Man United"], "AwayTeam": ["Arsenal"],
                        "FTHG": [1], "FTAG": [0], "FTR": ["H"], "AvgCH": [1.8], "AvgCD": [3.7], "AvgCA": [4.8]})
    frame = normalize_frame(raw, "2010-11", "E0")
    assert pd.isna(frame.iloc[0].home_shots)
    assert pd.isna(frame.iloc[0].market_prob_home)
    assert frame.iloc[0].closing_prob_home > 0
    assert frame.iloc[0].home_team == "Manchester United"
    assert "odds_raw_AvgCH" in frame


def test_odds_fallback_is_per_row_and_drops_incomplete_triplets():
    raw = pd.DataFrame({"Date": ["01/08/2020"], "HomeTeam": ["Arsenal"], "AwayTeam": ["Everton"],
                        "FTHG": [1], "FTAG": [0], "FTR": ["H"], "AvgH": [1.8], "AvgD": [None], "AvgA": [4.8],
                        "B365H": [2.0], "B365D": [3.0], "B365A": [4.0]})
    frame = normalize_frame(raw, "2020-21", "E0")
    assert frame.iloc[0].market_odds_source == "B365H/B365D/B365A"
    assert frame.iloc[0].market_prob_home == pytest.approx(6 / 13)


def test_aliases_and_value_floor():
    assert team_id("Manchester Utd") == team_id("Man United") == team_id("Manchester United")
    result = value_metrics(dict(home=.61, draw=.24, away=.15), dict(home=.72, draw=.18, away=.10))
    assert result["edge"]["home"] == pytest.approx(-.11)
    assert result["value"]["away"] == pytest.approx(1.5)
    zero = value_metrics(dict(home=.61, draw=.24, away=.15), dict(home=1, draw=0, away=0))
    assert zero["valueFloorApplied"]
    assert all(math.isfinite(v) for v in zero["value"].values())


def test_system_cost_and_invalid_selections():
    summary = system_cost([["1"], ["1", "X"], ["1", "X", "2"]])
    assert summary["rowCount"] == 6 and summary["cost"] == 6 * ROW_COST
    assert summary["singles"] == summary["doubles"] == summary["triples"] == 1
    for selections in ([], [[]], [["1", "1"]], [["H"]]):
        with pytest.raises(ValueError):
            system_cost(selections)


def example_matches(count=13):
    return [{"model": dict(home=.61, draw=.25, away=.14), "crowd": dict(home=.80, draw=.14, away=.06)} for _ in range(count)]


@pytest.mark.parametrize("budget", [1, 7, 64, 128, 256, 512, 513.5])
@pytest.mark.parametrize("mode", ["optimal", "safe", "value"])
def test_optimizer_respects_budget_and_is_deterministic(budget, mode):
    result = optimize(example_matches(), budget, mode)
    assert result["cost"] <= budget
    assert len(result["selections"]) == 13
    assert result["rowCount"] == math.prod(map(len, result["selections"]))
    assert result["singles"] + result["doubles"] + result["triples"] == 13
    assert result == optimize(example_matches(), budget, mode)


def test_dp_finds_brute_force_optimum_on_small_coupon():
    matches = example_matches(3)
    matches[1] = {"model": dict(home=.4, draw=.3, away=.3), "crowd": dict(home=.3, draw=.3, away=.4)}
    scores = []
    for selections in product(SUBSETS, repeat=3):
        if math.prod(map(len, selections)) <= 6:
            scores.append(sum(selection_score([m["model"][k] for k in OUTCOMES], [m["crowd"][k] for k in OUTCOMES], s, "optimal") for m, s in zip(matches, selections)))
    assert optimize(matches, 6, "optimal")["objectiveScore"] == pytest.approx(max(scores))


def test_modes_change_real_choices_and_overselected_favorite_is_penalized():
    safe = optimize(example_matches(), 64, "safe")
    value = optimize(example_matches(), 64, "value")
    assert safe["selections"] != value["selections"]
    attractive = selection_score([.70, .20, .10], [.58, .27, .15], (0,), "optimal")
    overselected = selection_score([.61, .25, .14], [.80, .14, .06], (0,), "optimal")
    assert attractive > overselected


def test_crowd_and_coupon_validation():
    assert sum(Crowd(home=33, draw=33, away=33).normalized().values()) == pytest.approx(1)
    for values in (dict(home=40, draw=20, away=20), dict(home=-1, draw=50, away=51), dict(home=float("nan"), draw=50, away=50)):
        with pytest.raises(ValidationError): Crowd(**values)
    coupon = demo_coupon()
    assert len(Coupon(**coupon).matches) == 13
    coupon["matches"][1]["number"] = 1
    with pytest.raises(ValidationError): Coupon(**coupon)


def test_missing_model_and_unknown_teams_use_honest_fallback(tmp_path):
    predictor = PredictionService(tmp_path)
    match = MatchInput(homeTeam="Unknown", awayTeam="Arsenal", date="2030-01-01", league="E0", marketOdds=dict(home=3, draw=3, away=2))
    result = predictor.predict(match)
    assert result["source"] == "market_fallback"
    assert result["model"] == result["market"]
    assert result["warnings"] and result["features"] == {}
    _, state = build_features(history())
    predictor.bundle = {"state": state, "metadata": {"data_through": "2020-08-15"}}
    predictor.load = lambda: None
    assert "Unknown" in predictor.predict(match)["warnings"][0]
    match.date = pd.Timestamp("2020-08-01").date()
    assert "träningshistorik" in predictor.predict(match)["warnings"][0]
