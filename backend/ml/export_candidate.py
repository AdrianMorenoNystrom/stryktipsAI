"""Persist the selected v2 challenger even when the market remains the active model."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import joblib
import pandas as pd
from threadpoolctl import threadpool_limits
from app.config import ARTIFACTS, DATA
from ml.correction import MarketCorrection
from ml.feature_engineering import build_features
from ml.train import period
from ml.v2_config import VARIANTS, feature_columns, RESIDUAL_PENALTIES


def export_candidate() -> dict:
    metadata = json.loads((ARTIFACTS / "model_metadata.json").read_text())
    evaluation = metadata["evaluation"]
    name = evaluation["selection"]["v2_candidate"]
    variant = VARIANTS[name]
    matches = pd.read_parquet(DATA / "processed" / "matches.parquet")
    matches = matches[matches.date <= pd.Timestamp(metadata["data_through"])]
    frame, state = build_features(matches, variant.get("regression", 1.0), variant.get("division_adjustment", 0.0))
    frame = frame.dropna(subset=["market_prob_home", "market_prob_draw", "market_prob_away"])
    numeric = feature_columns(list(frame), variant["groups"])
    record = evaluation["folds"][evaluation["auditSeason"]][name]
    model = MarketCorrection(numeric, record["selected_parameter"], variant.get("interactions", False))
    fit_data = frame[frame.season < evaluation["auditSeason"]] if variant.get("calibrate") else frame
    model.fit(fit_data, fit_data.target)
    if variant.get("calibrate"):
        calibration = frame[frame.season == evaluation["auditSeason"]]
        model.calibrate(calibration, calibration.target)
    columns = [*numeric, "league", "market_prob_home", "market_prob_draw", "market_prob_away"]
    challenger_metadata = {"modelVersion": "2.0", "modelType": "market-anchored-correction", "candidate": name,
        "active": metadata["activeModel"] == name, "features": columns, "parameters": variant, "fitPeriod": period(fit_data),
        "temperature": model.temperature, "penalty": model.penalty, "newsAffectsProbabilities": False,
        "dataset_sha256": metadata["dataset_sha256"]}
    joblib.dump({"model": model, "features": columns, "state": state, "metadata": challenger_metadata}, ARTIFACTS / "model_v2_candidate.joblib")
    (ARTIFACTS / "model_v2_candidate_metadata.json").write_text(json.dumps(challenger_metadata, indent=2), encoding="utf-8")
    (ARTIFACTS / "experiment_manifest.json").write_text(json.dumps({"variants": VARIANTS, "penalties": RESIDUAL_PENALTIES, "selection": evaluation["selection"]}, indent=2), encoding="utf-8")
    return challenger_metadata


if __name__ == "__main__":
    with threadpool_limits(limits=1):
        print(json.dumps(export_candidate(), indent=2))
