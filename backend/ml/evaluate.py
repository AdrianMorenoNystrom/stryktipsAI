import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, log_loss
from app.config import ARTIFACTS
from ml.v2_config import CALIBRATION_BIN_COUNT


def metrics(target: np.ndarray, probabilities: np.ndarray) -> dict:
    truth = np.eye(3)[target.astype(int)]
    calibration = []
    class_ece = []
    for outcome in range(3):
        bins = []
        bin_ids = np.minimum((probabilities[:, outcome] * CALIBRATION_BIN_COUNT).astype(int), CALIBRATION_BIN_COUNT - 1)
        ece = 0.0
        for index in range(CALIBRATION_BIN_COUNT):
            mask = bin_ids == index
            if mask.any():
                predicted, observed = probabilities[mask, outcome].mean(), truth[mask, outcome].mean()
                ece += float(mask.mean() * abs(predicted - observed))
                bins.append({"lower": index / CALIBRATION_BIN_COUNT, "upper": (index + 1) / CALIBRATION_BIN_COUNT,
                             "count": int(mask.sum()), "predicted": float(probabilities[mask, outcome].mean()),
                             "observed": float(truth[mask, outcome].mean())})
        calibration.append(bins)
        class_ece.append(ece)
    return {"log_loss": float(log_loss(target, probabilities, labels=[0, 1, 2])),
            "brier_score": float(np.mean(np.sum((probabilities - truth) ** 2, axis=1))),
            "accuracy": float(accuracy_score(target, probabilities.argmax(axis=1))),
            "calibration": calibration, "ece": float(np.mean(class_ece)), "class_ece": class_ece, "matches": len(target)}


def evaluate() -> dict:
    frame = pd.read_parquet(ARTIFACTS / "test_predictions.parquet")
    result = {kind: metrics(frame.target.to_numpy(), frame[[f"{kind}_{i}" for i in range(3)]].to_numpy())
              for kind in ("market", "ml")}
    (ARTIFACTS / "evaluation.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    print(json.dumps(evaluate(), indent=2))
