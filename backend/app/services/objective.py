"""Additive, separable heuristic. See docs/optimizer.md for mathematical definition."""
from math import log
from app.config import OPTIMIZER_WEIGHTS, VALUE_FLOOR


def selection_score(model: list[float], crowd: list[float], subset: tuple[int, ...], mode: str) -> float:
    a, b, c, d = OPTIMIZER_WEIGHTS[mode]
    coverage = sum(model[i] for i in subset)
    edge = sum(model[i] * (model[i] - crowd[i]) for i in subset) / coverage
    value = sum(model[i] * log(max(model[i], 1e-12) / max(crowd[i], VALUE_FLOOR)) for i in subset) / coverage
    return a * log(max(coverage, 1e-12)) + b * edge + c * value - d * log(len(subset))
