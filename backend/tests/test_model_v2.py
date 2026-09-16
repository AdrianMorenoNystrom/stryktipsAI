import json
import numpy as np
import pandas as pd
import pytest
from threadpoolctl import threadpool_limits
from app.config import ARTIFACTS, ELO_INITIAL
from app.schemas import MatchInput
from ml.correction import MarketBaseline, MarketCorrection
from ml.feature_engineering import FeatureState
from ml.evaluate import metrics
from ml.v2_config import feature_columns
from ml.walk_forward import Fold, folds, fit_fold
from ml.predict import PredictionService


def training_frame() -> pd.DataFrame:
    records = []
    for year in range(2016, 2026):
        for i in range(30):
            records.append({"match_id": f"{year}-{i}", "season": f"{year}-{str(year+1)[-2:]}",
                "date": pd.Timestamp(year=year, month=8, day=i % 28 + 1), "league": ["E0", "E1", "E2"][i % 3],
                "target": i % 3, "elo_difference": float((i % 5) * 15), "home_points_avg_5": float(i % 4),
                "home_venue_points_avg_5": float(i % 3), "rest_difference": float(i % 2),
                "market_prob_home": .45, "market_prob_draw": .30, "market_prob_away": .25})
    return pd.DataFrame(records)


def test_market_is_exact_anchor_and_residual_simplex_reproducibility():
    frame = training_frame()
    original = frame[["market_prob_home", "market_prob_draw", "market_prob_away"]].to_numpy().copy()
    np.testing.assert_array_equal(MarketBaseline().predict_proba(frame), original)
    with threadpool_limits(limits=1):
        model = MarketCorrection(["elo_difference"]).fit(frame, frame.target)
        repeated = MarketCorrection(["elo_difference"]).fit(frame, frame.target)
    p = model.predict_proba(frame)
    np.testing.assert_allclose(p.sum(axis=1), 1, atol=1e-12)
    assert (p > 0).all()
    np.testing.assert_allclose(p, repeated.predict_proba(frame), atol=1e-12)
    model.weights[:] = 0
    np.testing.assert_allclose(model.predict_proba(frame), original, atol=1e-15)
    np.testing.assert_array_equal(frame[["market_prob_home", "market_prob_draw", "market_prob_away"]].to_numpy(), original)


def test_walk_forward_strict_order_and_shared_ablation_periods():
    frame = training_frame()
    schedule = folds(frame)
    assert len(schedule) == 6
    for fold in schedule:
        train, validation, test = fold.split(frame)
        assert train.date.max() < validation.date.min() < test.date.min()
    groups = [["elo"], ["elo", "form"], ["elo", "form", "venue"], ["elo", "form", "venue", "rest"]]
    assert [len(feature_columns(list(frame), group)) for group in groups] == [1, 2, 3, 4]
    with threadpool_limits(limits=1):
        records = [fit_fold(frame, schedule[-1], {"groups": group})[1] for group in groups]
    assert all(record["test"] == records[0]["test"] for record in records)


def test_calibration_and_tuning_never_use_test_outcomes():
    frame = training_frame()
    fold = Fold("2024-25", "2025-26")
    changed = frame.copy()
    changed.loc[changed.season == fold.test, "target"] = 2
    with threadpool_limits(limits=1):
        first, record = fit_fold(frame, fold, {"groups": ["elo"], "calibrate": True})
        second, altered = fit_fold(changed, fold, {"groups": ["elo"], "calibrate": True})
    np.testing.assert_allclose(first, second, atol=1e-12)
    assert record["selected_parameter"] == altered["selected_parameter"]
    assert record["final_fit"]["to"] < record["calibration"]["from"]
    assert record["calibration"]["to"] < record["test"]["from"]


def test_season_transition_preserves_history_and_only_uses_prior_state():
    state = FeatureState(season_regression=.85, division_adjustment=75)
    promoted = state.teams["promoted"]
    promoted.elo, promoted.season, promoted.league, promoted.total = 1600, "2024-25", "E1", 40
    state.teams["established"].elo, state.teams["established"].league = 1700, "E0"
    state.begin_day([{"home_team_id": "promoted", "away_team_id": "established", "league": "E0", "season": "2025-26"}])
    assert promoted.elo == pytest.approx(1700 + .85 * (1600 - 1700) - 75)
    assert promoted.total == 40
    same_elo = promoted.elo
    state.begin_day([{"home_team_id": "promoted", "away_team_id": "established", "league": "E0", "season": "2025-26"}])
    assert promoted.elo == same_elo


def test_calibration_bins_partition_every_observation_once():
    probabilities = np.array([[.4, .3, .3], [.7, .2, .1], [1, 0, 0]])
    score = metrics(np.array([0, 1, 2]), probabilities)
    assert all(sum(bin["count"] for bin in bins) == 3 for bins in score["calibration"])
    assert 0 <= score["ece"] <= 1


def test_deployment_selection_excludes_audit_and_market_is_labeled():
    path = ARTIFACTS / "evaluation_v2.json"
    if not path.exists():
        pytest.skip("Run train_v2.py for actual artifact verification")
    report = json.loads(path.read_text())
    assert report["auditSeason"] not in report["selection"]["development_seasons"]
    for season, variants in report["folds"].items():
        periods = [v["test"] for v in variants.values()]
        assert all(p == periods[0] for p in periods)
    predictor = PredictionService()
    match = MatchInput(homeTeam="Arsenal", awayTeam="Everton", date="2030-01-01", league="E0", marketOdds={"home":1.8,"draw":3.5,"away":4.5})
    result = predictor.predict(match)
    if report["selection"]["active"] == "market":
        assert result["source"] == "market_baseline"
        assert result["model"] == result["market"]
    assert result["newsAffectsProbabilities"] is False
