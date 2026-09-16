"""Run predeclared walk-forward experiments; select on development folds, audit last fold."""
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import joblib
import pandas as pd
from threadpoolctl import threadpool_limits
from app.config import ARTIFACTS, DATA, SEED
from ml.correction import MarketBaseline, MarketCorrection, market_probabilities
from ml.diagnostics import ablation_report, diagnostics, score_models
from ml.feature_engineering import build_features
from ml.train import make_model, period
from ml.v2_config import MAX_ECE_REGRESSION, MIN_LOG_LOSS_GAIN, MIN_WINNING_SEASON_FRACTION, VARIANTS, feature_columns
from ml.walk_forward import fit_fold, folds


def select_model(development: pd.DataFrame) -> dict:
    ablation = ablation_report(development, ["v1", *VARIANTS])
    ranking = sorted(VARIANTS, key=lambda name: (ablation[name]["log_loss"], ablation[name]["brier_score"], ablation[name]["ece"], -ablation[name]["winning_seasons"]))
    v2 = ranking[0]
    candidates = [v2, "v1"]
    eligible = [name for name in candidates if
                ablation[name]["delta_log_loss"] <= -MIN_LOG_LOSS_GAIN and ablation[name]["delta_brier"] <= 0
                and ablation[name]["ece"] <= ablation["market"]["ece"] + MAX_ECE_REGRESSION
                and ablation[name]["winning_seasons"] / development.season.nunique() >= MIN_WINNING_SEASON_FRACTION]
    active = min(eligible, key=lambda name: (ablation[name]["log_loss"], ablation[name]["brier_score"], ablation[name]["ece"])) if eligible else "market"
    return {"v2_candidate": v2, "active": active, "development_seasons": sorted(development.season.unique().tolist()),
            "gates": {"min_log_loss_gain": MIN_LOG_LOSS_GAIN, "brier_must_not_worsen": True,
                      "max_ece_regression": MAX_ECE_REGRESSION, "min_winning_season_fraction": MIN_WINNING_SEASON_FRACTION},
            "eligible": eligible, "ranking": ranking,
            "reason": "Bäst godkända walk-forward-resultat före auditsäsongen." if eligible else "Ingen korrigering klarade alla fördefinierade kvalitetskrav. Marknaden förblir aktiv."}


def train_v2() -> dict:
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    archive = ARTIFACTS / "v1"
    if not archive.exists():
        archive.mkdir()
        for name in ("model.joblib", "model_metadata.json", "evaluation_model.joblib", "test_predictions.parquet", "evaluation.json"):
            if (ARTIFACTS / name).exists():
                shutil.copy2(ARTIFACTS / name, archive / name)
    source = DATA / "processed" / "matches.parquet"
    matches = pd.read_parquet(source)
    matches = matches[matches.date < pd.Timestamp.now().normalize()].copy()
    datasets = {}
    for regression, adjustment in sorted({(1.0, 0.0), *[(v.get("regression", 1.0), v.get("division_adjustment", 0.0)) for v in VARIANTS.values()]}):
        print(f"Features regression={regression}, division_adjustment={adjustment}", flush=True)
        frame, state = build_features(matches, regression, adjustment)
        frame = frame.dropna(subset=["market_prob_home", "market_prob_draw", "market_prob_away"])
        datasets[(regression, adjustment)] = (frame, state)
    base, _ = datasets[(1.0, 0.0)]
    schedule = folds(base)
    if len(schedule) < 3:
        raise ValueError("At least three walk-forward seasons are required")
    outputs, fold_records = [], {}
    for fold in schedule:
        test = base[base.season == fold.test]
        result = test[["match_id", "date", "season", "league", "target"]].copy()
        for i in range(3):
            result[f"market_{i}"] = market_probabilities(test)[:, i]
        fold_records[fold.test] = {}
        for name, variant in [("v1", None), *VARIANTS.items()]:
            setting = (variant.get("regression", 1.0), variant.get("division_adjustment", 0.0)) if variant else (1.0, 0.0)
            frame, _ = datasets[setting]
            assert frame[frame.season == fold.test].match_id.tolist() == test.match_id.tolist()
            probabilities, record = fit_fold(frame, fold, variant)
            for i in range(3):
                result[f"{name}_{i}"] = probabilities[:, i]
            fold_records[fold.test][name] = record
            print(f"{fold.test}: {name} complete", flush=True)
        outputs.append(result)
        pd.concat(outputs).to_parquet(ARTIFACTS / "walk_forward_progress.parquet", index=False)
    predictions = pd.concat(outputs, ignore_index=True)
    audit_season = schedule[-1].test
    development = predictions[predictions.season < audit_season]
    selection = select_model(development)
    for i in range(3):
        predictions[f"v2_{i}"] = predictions[f"{selection['v2_candidate']}_{i}"]
        predictions[f"active_{i}"] = predictions[f"{selection['active']}_{i}"]
    evaluation = diagnostics(predictions, ["market", "v1", "v2", "active"])
    evaluation["ablation"] = ablation_report(predictions, list(VARIANTS))
    evaluation["developmentAblation"] = ablation_report(development, list(VARIANTS))
    evaluation["folds"] = fold_records
    evaluation["selection"] = selection
    evaluation["auditSeason"] = audit_season
    evaluation["audit"] = score_models(predictions[predictions.season == audit_season], ["market", "v1", "v2", "active"])
    # Deployment refit uses the latest nested fold's pre-test chosen hyperparameters.
    active = selection["active"]
    variant = VARIANTS.get(active, {})
    frame, state = datasets[(variant.get("regression", 1.0), variant.get("division_adjustment", 0.0))]
    if active == "market":
        model, columns = MarketBaseline(), ["market_prob_home", "market_prob_draw", "market_prob_away"]
    elif active == "v1":
        columns = [c for c in frame if c not in ("match_id", "date", "season", "target")]
        model = make_model([c for c in columns if c != "league"], fold_records[audit_season][active]["selected_parameter"]).fit(frame, frame.target)
    else:
        numeric = feature_columns(list(frame.columns), variant["groups"])
        columns = [*numeric, "league", "market_prob_home", "market_prob_draw", "market_prob_away"]
        model = MarketCorrection(numeric, fold_records[audit_season][active]["selected_parameter"], variant.get("interactions", False))
        if variant.get("calibrate"):
            calibration_season = audit_season
            fit_data = frame[frame.season < calibration_season]
            calibration_data = frame[frame.season == calibration_season]
            model.fit(fit_data, fit_data.target).calibrate(calibration_data, calibration_data.target)
        else:
            model.fit(frame, frame.target)
    old_metadata = json.loads((archive / "model_metadata.json").read_text()) if (archive / "model_metadata.json").exists() else {}
    legacy = {key: old_metadata.pop(key) for key in ("split", "test", "validation", "validation_candidates", "selected_C") if key in old_metadata}
    metadata = {**old_metadata, "modelVersion": "2.0", "modelType": "market-baseline" if active == "market" else "legacy-logistic" if active == "v1" else "market-anchored-correction",
                "legacyV1": legacy,
                "activeModel": active, "activeModelLabel": "Marknadsbaseline" if active == "market" else "Model v1" if active == "v1" else "Market-Anchored v2",
                "trained_at": datetime.now(timezone.utc).isoformat(), "training_matches": len(frame),
                "features": columns, "feature_version": 2, "seed": SEED,
                "feature_config": {"season_regression": variant.get("regression", 1.0), "division_adjustment": variant.get("division_adjustment", 0.0)},
                "data_through": str(matches.date.max().date()), "dataset_matches": len(matches), "dataset_leagues": matches.league.value_counts().to_dict(),
                "dataset_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                "evaluation": evaluation, "newsAffectsProbabilities": False,
                "log_loss": evaluation["overall"]["active"]["log_loss"], "brier_score": evaluation["overall"]["active"]["brier_score"],
                "accuracy": evaluation["overall"]["active"]["accuracy"],
                "deploymentPeriod": period(frame),
                "evaluation_policy": "Nested chronological tuning, predeclared development-season selection, final-season audit; aggregated chosen-v2 development scores are selection results, not independent confirmation."}
    temporary = ARTIFACTS / "model.v2.tmp"
    joblib.dump({"model": model, "features": columns, "state": state, "metadata": metadata}, temporary)
    temporary.replace(ARTIFACTS / "model.joblib")
    (ARTIFACTS / "model_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    (ARTIFACTS / "evaluation_v2.json").write_text(json.dumps(evaluation, indent=2), encoding="utf-8")
    predictions.to_parquet(ARTIFACTS / "walk_forward_predictions.parquet", index=False)
    print(json.dumps(selection, indent=2, ensure_ascii=False), flush=True)
    return metadata


if __name__ == "__main__":
    with threadpool_limits(limits=1):
        train_v2()
        from ml.export_candidate import export_candidate
        export_candidate()
