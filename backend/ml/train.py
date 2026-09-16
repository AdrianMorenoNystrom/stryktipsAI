"""Chronological model selection and untouched final season evaluation."""
import hashlib
import importlib.metadata
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from app.config import ARTIFACTS, DATA, MAX_TRAIN_ITERATIONS, REGULARIZATION_CANDIDATES, SEED, current_season
from app.config import ELO_HOME_ADVANTAGE, ELO_INITIAL, ELO_K, MIN_HISTORY, ROLLING_WINDOWS
from ml.evaluate import metrics
from ml.feature_engineering import FEATURE_VERSION, build_features


def make_model(numeric: list[str], regularization: float) -> Pipeline:
    numeric_pipeline = Pipeline([("imputer", SimpleImputer(strategy="median", keep_empty_features=True)),
                                 ("scale", StandardScaler())])
    transform = ColumnTransformer([("numeric", numeric_pipeline, numeric),
                                   ("league", OneHotEncoder(handle_unknown="ignore", sparse_output=False), ["league"])])
    return Pipeline([("features", transform),
                     ("model", LogisticRegression(C=regularization, max_iter=MAX_TRAIN_ITERATIONS, random_state=SEED))])


def period(frame: pd.DataFrame) -> dict:
    return {"from": str(frame.date.min().date()), "to": str(frame.date.max().date()),
            "seasons": sorted(frame.season.unique().tolist()), "matches": len(frame)}


def train() -> dict:
    source = DATA / "processed" / "matches.parquet"
    if not source.exists():
        raise FileNotFoundError("Dataset saknas. Kör normalisering först.")
    matches = pd.read_parquet(source)
    # A malformed source must not introduce future outcomes into training.
    matches = matches[matches.date < pd.Timestamp.now().normalize()].copy()
    frame, state = build_features(matches)
    frame = frame.dropna(subset=["market_prob_home", "market_prob_draw", "market_prob_away"])
    completed = sorted(s for s in frame.season.unique() if int(s[:4]) < current_season())
    if len(completed) < 3:
        raise ValueError("Minst tre avslutade säsonger med odds krävs för temporal utvärdering.")
    validation_season, test_season = completed[-2:]
    training = frame[frame.season < validation_season]
    validation = frame[frame.season == validation_season]
    test = frame[frame.season == test_season]
    if any(set(part.target.unique()) != {0, 1, 2} for part in (training, validation, test)):
        raise ValueError("Alla tre utfall måste finnas i train, validation och test.")
    excluded = {"match_id", "date", "season", "target"}
    features = [c for c in frame if c not in excluded]
    numeric = [c for c in features if c != "league"]
    candidates = []
    best_model, best_loss, best_c = None, float("inf"), 0.0
    for c in REGULARIZATION_CANDIDATES:
        model = make_model(numeric, c)
        model.fit(training[features], training.target)
        score = metrics(validation.target.to_numpy(), model.predict_proba(validation[features]))
        candidates.append({"C": c, **{k: v for k, v in score.items() if k != "calibration"}})
        if score["log_loss"] < best_loss:
            best_model, best_loss, best_c = model, score["log_loss"], c
    assert best_model is not None
    validation_metrics = {
        "market": metrics(validation.target.to_numpy(), validation[[f"market_prob_{k}" for k in ("home", "draw", "away")]].to_numpy()),
        "ml": metrics(validation.target.to_numpy(), best_model.predict_proba(validation[features])),
    }
    # Refitting on validation is safe only after hyperparameters are selected.
    pre_test = frame[frame.season < test_season]
    evaluation_model = make_model(numeric, best_c).fit(pre_test[features], pre_test.target)
    ml_probabilities = evaluation_model.predict_proba(test[features])
    market_probabilities = test[[f"market_prob_{k}" for k in ("home", "draw", "away")]].to_numpy()
    test_metrics = {"market": metrics(test.target.to_numpy(), market_probabilities),
                    "ml": metrics(test.target.to_numpy(), ml_probabilities)}
    # Deployment uses all available history; test metrics belong to the frozen evaluation model.
    production_model = make_model(numeric, best_c).fit(frame[features], frame.target)
    metadata = {
        "trained_at": datetime.now(timezone.utc).isoformat(), "training_matches": len(frame),
        "dataset_matches": len(matches), "dataset_leagues": matches.league.value_counts().to_dict(),
        "leagues": sorted(matches.league.unique().tolist()), "seasons": sorted(frame.season.unique().tolist()),
        "features": features, "feature_version": FEATURE_VERSION, "seed": SEED, "selected_C": best_c,
        "feature_config": {"elo_initial": ELO_INITIAL, "elo_home_advantage": ELO_HOME_ADVANTAGE,
                           "elo_k": ELO_K, "rolling_windows": ROLLING_WINDOWS, "min_history": MIN_HISTORY},
        "team_aliases_sha256": hashlib.sha256((Path(__file__).resolve().parents[1] / "app" / "team_aliases.json").read_bytes()).hexdigest(),
        "split": {"train": period(training), "validation": period(validation), "test": period(test),
                  "evaluation_fit": period(pre_test), "production_fit": period(frame)},
        "validation_candidates": candidates, "validation": validation_metrics, "test": test_metrics,
        "log_loss": test_metrics["ml"]["log_loss"], "brier_score": test_metrics["ml"]["brier_score"],
        "accuracy": test_metrics["ml"]["accuracy"], "data_through": str(matches.date.max().date()),
        "dataset_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "versions": {name: importlib.metadata.version(name) for name in ("numpy", "pandas", "scikit-learn", "joblib", "pyarrow")},
        "python": platform.python_version(), "odds_policy": "Non-closing aggregate odds, then non-closing bookmaker fallback; no exact historical observation time.",
        "evaluation_policy": "Sequential pre-match features; model weights fixed before test. Daily results update form and Elo throughout test.",
    }
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    predictions = test[["match_id", "date", "target"]].copy()
    for index in range(3):
        predictions[f"ml_{index}"] = ml_probabilities[:, index]
        predictions[f"market_{index}"] = market_probabilities[:, index]
    predictions.to_parquet(ARTIFACTS / "test_predictions.parquet", index=False)
    joblib.dump({"model": evaluation_model, "features": features}, ARTIFACTS / "evaluation_model.joblib")
    artifact = ARTIFACTS / "model.joblib"
    temporary = artifact.with_suffix(".tmp")
    joblib.dump({"model": production_model, "features": features, "state": state, "metadata": metadata}, temporary)
    temporary.replace(artifact)
    (ARTIFACTS / "model_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    (DATA / "processed" / "features.parquet").parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(DATA / "processed" / "features.parquet", index=False)
    return metadata


if __name__ == "__main__":
    result = train()
    print(json.dumps({k: result[k] for k in ("training_matches", "dataset_leagues", "split", "log_loss", "brier_score", "accuracy")}, indent=2))
