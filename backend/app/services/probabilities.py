import math
from app.config import OUTCOMES, VALUE_FLOOR


def devig(odds: dict[str, float]) -> dict[str, float]:
    if any(not math.isfinite(odds[k]) or odds[k] <= 1 for k in OUTCOMES):
        raise ValueError("Alla tre odds måste vara ändliga tal större än 1.")
    inverse = {k: 1 / odds[k] for k in OUTCOMES}
    total = sum(inverse.values())
    return {k: v / total for k, v in inverse.items()}


def value_metrics(model: dict[str, float], crowd: dict[str, float]) -> dict:
    return {
        "edge": {k: model[k] - crowd[k] for k in OUTCOMES},
        "value": {k: model[k] / max(crowd[k], VALUE_FLOOR) for k in OUTCOMES},
        "valueFloorApplied": any(crowd[k] < VALUE_FLOOR for k in OUTCOMES),
    }
