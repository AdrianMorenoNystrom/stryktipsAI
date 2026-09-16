"""Regularized multinomial correction with fixed log(market) offsets.

Minimizes mean cross entropy + lambda/2 * ||W||², including intercept.
At W=0 and temperature=1 prediction is exactly the supplied market.
"""
import numpy as np
import pandas as pd
from scipy.optimize import minimize, minimize_scalar
from scipy.special import logsumexp, softmax
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from ml.v2_config import MARKET_COLUMNS


class MarketBaseline:
    def predict_proba(self, frame: pd.DataFrame) -> np.ndarray:
        return market_probabilities(frame)


def market_probabilities(frame: pd.DataFrame) -> np.ndarray:
    probabilities = frame[MARKET_COLUMNS].to_numpy(dtype=float)
    if not np.isfinite(probabilities).all() or (probabilities <= 0).any():
        raise ValueError("Market probabilities must be positive and finite")
    if not np.allclose(probabilities.sum(axis=1), 1, atol=1e-8):
        raise ValueError("Market probabilities must sum to one")
    return probabilities


class MarketCorrection:
    def __init__(self, numeric: list[str], penalty: float = .1, interactions: bool = False) -> None:
        self.numeric = numeric
        self.penalty = penalty
        self.interactions = interactions
        self.temperature = 1.0

    def design(self, frame: pd.DataFrame, fit: bool = False) -> np.ndarray:
        if fit:
            self.imputer = SimpleImputer(strategy="median", keep_empty_features=True)
            self.scaler = StandardScaler()
            numeric = self.scaler.fit_transform(self.imputer.fit_transform(frame[self.numeric]))
        else:
            numeric = self.scaler.transform(self.imputer.transform(frame[self.numeric]))
        league = np.column_stack([(frame.league == value).astype(float) for value in ("E0", "E1", "E2")])
        parts = [np.ones((len(frame), 1)), numeric, league[:, 1:]]
        if self.interactions:
            parts += [numeric * league[:, i:i + 1] for i in (1, 2)]
        return np.column_stack(parts)

    def fit(self, frame: pd.DataFrame, target: np.ndarray) -> "MarketCorrection":
        x = self.design(frame, fit=True)
        offset = np.log(market_probabilities(frame))
        truth = np.eye(3)[np.asarray(target, dtype=int)]
        def loss_gradient(flat: np.ndarray) -> tuple[float, np.ndarray]:
            weights = flat.reshape(x.shape[1], 3)
            logits = offset + x @ weights
            loss = np.mean(logsumexp(logits, axis=1) - np.sum(truth * logits, axis=1))
            gradient = x.T @ (softmax(logits, axis=1) - truth) / len(x) + self.penalty * weights
            return float(loss + self.penalty * np.sum(weights ** 2) / 2), gradient.ravel()
        result = minimize(loss_gradient, np.zeros(x.shape[1] * 3), jac=True, method="L-BFGS-B",
                          options={"maxiter": 500, "ftol": 1e-11, "gtol": 1e-7})
        if not result.success:
            raise RuntimeError(f"Residual fit did not converge: {result.message}")
        self.weights = result.x.reshape(x.shape[1], 3)
        self.iterations = int(result.nit)
        return self

    def predict_proba(self, frame: pd.DataFrame) -> np.ndarray:
        logits = np.log(market_probabilities(frame)) + self.design(frame) @ self.weights
        return softmax(logits / self.temperature, axis=1)

    def calibrate(self, validation: pd.DataFrame, target: np.ndarray) -> float:
        # This method must receive only the separate pre-test calibration season.
        logits = np.log(market_probabilities(validation)) + self.design(validation) @ self.weights
        truth = np.eye(3)[np.asarray(target, dtype=int)]
        def loss(temperature: float) -> float:
            scaled = logits / temperature
            return float(np.mean(logsumexp(scaled, axis=1) - np.sum(truth * scaled, axis=1)))
        result = minimize_scalar(loss, bounds=(0.7, 1.5), method="bounded", options={"xatol": 1e-7})
        self.temperature = float(result.x)
        return self.temperature
