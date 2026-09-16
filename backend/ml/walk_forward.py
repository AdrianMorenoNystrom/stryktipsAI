from dataclasses import dataclass
import numpy as np
import pandas as pd
from ml.correction import MarketCorrection
from ml.evaluate import metrics
from ml.train import make_model, period
from ml.v2_config import FIRST_TEST_SEASON, RESIDUAL_PENALTIES, feature_columns
from app.config import REGULARIZATION_CANDIDATES, current_season


@dataclass(frozen=True)
class Fold:
    validation: str
    test: str

    def split(self, frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        train, validation, test = (frame[frame.season < self.validation], frame[frame.season == self.validation], frame[frame.season == self.test])
        if any(part.empty for part in (train, validation, test)):
            raise ValueError("Empty temporal partition")
        if not train.date.max() < validation.date.min() <= validation.date.max() < test.date.min():
            raise ValueError("Temporal partitions overlap")
        return train, validation, test


def folds(frame: pd.DataFrame, first: int = FIRST_TEST_SEASON) -> list[Fold]:
    seasons = sorted(s for s in frame.season.unique() if int(s[:4]) < current_season())
    return [Fold(seasons[i - 1], season) for i, season in enumerate(seasons) if i >= 2 and int(season[:4]) >= first]


def fit_fold(frame: pd.DataFrame, fold: Fold, variant: dict | None) -> tuple[np.ndarray, dict]:
    training, validation, test = fold.split(frame)
    if variant is None:
        columns = [c for c in frame if c not in ("match_id", "date", "season", "target", "league")]
        choices = REGULARIZATION_CANDIDATES
        create = lambda value: make_model(columns, value)
    else:
        columns = feature_columns(list(frame.columns), variant["groups"])
        choices = RESIDUAL_PENALTIES
        create = lambda value: MarketCorrection(columns, value, variant.get("interactions", False))
    best_model, best_value, best_score = None, 0.0, float("inf")
    candidates = []
    for value in choices:
        model = create(value).fit(training, training.target.to_numpy())
        score = metrics(validation.target.to_numpy(), model.predict_proba(validation))
        candidates.append({"value": value, "log_loss": score["log_loss"], "brier_score": score["brier_score"], "ece": score["ece"]})
        if score["log_loss"] < best_score:
            best_model, best_value, best_score = model, value, score["log_loss"]
    if variant and variant.get("calibrate"):
        best_model.calibrate(validation, validation.target.to_numpy())
        fit_period = period(training)
    else:
        pre_test = frame[frame.season < fold.test]
        best_model = create(best_value).fit(pre_test, pre_test.target.to_numpy())
        fit_period = period(pre_test)
    return best_model.predict_proba(test), {
        "test_season": fold.test, "train": period(training), "validation": period(validation), "test": period(test),
        "final_fit": fit_period, "calibration": period(validation) if variant and variant.get("calibrate") else None,
        "selected_parameter": best_value, "temperature": getattr(best_model, "temperature", 1.0),
        "candidates": candidates, "features": columns,
    }
