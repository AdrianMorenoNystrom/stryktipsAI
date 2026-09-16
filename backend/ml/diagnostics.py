import numpy as np
import pandas as pd
from ml.evaluate import metrics


def score_models(frame: pd.DataFrame, models: list[str]) -> dict:
    if frame.empty:
        return {model: None for model in models}
    return {model: metrics(frame.target.to_numpy(), frame[[f"{model}_{i}" for i in range(3)]].to_numpy()) for model in models}


def diagnostics(frame: pd.DataFrame, models: list[str]) -> dict:
    market = frame[[f"market_{i}" for i in range(3)]].to_numpy()
    maximum = market.max(axis=1)
    gap = np.sort(market, axis=1)[:, -1] - np.sort(market, axis=1)[:, -2]
    buckets = {
        "favourite_<40": maximum < .4, "favourite_40-50": (maximum >= .4) & (maximum < .5),
        "favourite_50-60": (maximum >= .5) & (maximum < .6), "favourite_60-70": (maximum >= .6) & (maximum < .7),
        "favourite_70+": maximum >= .7,
        "very_even": gap < .1, "moderately_even": (gap >= .1) & (gap < .25),
        "clear_favourite": (gap >= .25) & (gap < .45), "heavy_favourite": gap >= .45,
        "home_favourite": market.argmax(axis=1) == 0, "away_favourite": market.argmax(axis=1) == 2,
        "draw_heavy": market[:, 1] >= .3,
        "early_season": frame.date.dt.month.isin([7, 8, 9, 10]).to_numpy(),
        "mid_season": frame.date.dt.month.isin([11, 12, 1, 2]).to_numpy(),
        "late_season": frame.date.dt.month.isin([3, 4, 5, 6]).to_numpy(),
    }
    disagreement = {}
    for model in models:
        if model == "market":
            continue
        difference = np.abs(frame[[f"{model}_{i}" for i in range(3)]].to_numpy() - market).max(axis=1)
        disagreement[model] = {}
        for label, low, high in (("0-2pp", 0, .02), ("2-5pp", .02, .05), ("5-8pp", .05, .08), ("8+pp", .08, 1.01)):
            selected = frame[(difference >= low) & (difference < high)]
            scores = score_models(selected, ["market", model])
            disagreement[model][label] = {"matches": len(selected), "scores": scores,
                "delta_log_loss": scores[model]["log_loss"] - scores["market"]["log_loss"] if len(selected) else None}
    return {"overall": score_models(frame, models),
            "byLeague": {league: score_models(group, models) for league, group in frame.groupby("league")},
            "bySeason": {season: score_models(group, models) for season, group in frame.groupby("season")},
            "byMarketBucket": {name: score_models(frame[mask], models) for name, mask in buckets.items()},
            "disagreement": disagreement,
            "bucketDefinitions": {"disagreement": "max absolute difference across 1/X/2", "balance": "largest minus second-largest market probability",
                                  "draw_heavy": "market draw >= 30%", "season_phase": "calendar months; COVID schedule shifts not corrected"}}


def ablation_report(frame: pd.DataFrame, names: list[str]) -> dict:
    baseline = score_models(frame, ["market"])["market"]
    result = {}
    for name in ["market", *names]:
        scores = score_models(frame, [name])[name]
        by_season = {}
        for season, group in frame.groupby("season"):
            pair = score_models(group, ["market", name])
            by_season[season] = pair[name]["log_loss"] - pair["market"]["log_loss"]
        result[name] = {**scores, "delta_log_loss": scores["log_loss"] - baseline["log_loss"],
                        "delta_brier": scores["brier_score"] - baseline["brier_score"], "season_deltas": by_season,
                        "winning_seasons": sum(value < 0 for value in by_season.values())}
    return result
