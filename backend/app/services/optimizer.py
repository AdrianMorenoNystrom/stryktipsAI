from decimal import Decimal, ROUND_FLOOR
from itertools import combinations
from math import exp, log, prod
from app.config import OUTCOMES, ROW_COST, SIGNS, VALUE_FLOOR
from app.services.objective import selection_score

SUBSETS = tuple(subset for size in (1, 2, 3) for subset in combinations(range(3), size))


def system_cost(selections: list[list[str]]) -> dict:
    if not selections or any(not s or len(set(s)) != len(s) or not set(s).issubset(SIGNS) for s in selections):
        raise ValueError("Varje match måste ha 1–3 unika tecken.")
    sizes = [len(s) for s in selections]
    rows = prod(sizes)
    return {"rowCount": rows, "cost": float(Decimal(rows) * Decimal(str(ROW_COST))), "costPerRow": ROW_COST,
            "singles": sizes.count(1), "doubles": sizes.count(2), "triples": sizes.count(3)}


def optimize(matches: list[dict], budget: float, mode: str) -> dict:
    max_rows = int((Decimal(str(budget)) / Decimal(str(ROW_COST))).to_integral_value(rounding=ROUND_FLOOR))
    if max_rows < 1:
        raise ValueError("Budgeten räcker inte till en rad.")
    # Exact DP over reachable products 2^d * 3^t, not 7^13 enumerated systems.
    states: dict[int, tuple[float, tuple]] = {1: (0.0, ())}
    for match in matches:
        model = [match["model"][k] for k in OUTCOMES]
        crowd = [match["crowd"][k] for k in OUTCOMES]
        scores = [(subset, selection_score(model, crowd, subset, mode)) for subset in SUBSETS]
        next_states: dict[int, tuple[float, tuple]] = {}
        for rows, (score, selections) in sorted(states.items()):
            for subset, contribution in scores:
                new_rows = rows * len(subset)
                if new_rows > max_rows:
                    continue
                candidate = (score + contribution, selections + (subset,))
                if new_rows not in next_states or candidate[0] > next_states[new_rows][0] + 1e-12:
                    next_states[new_rows] = candidate
        states = next_states
    rows, (score, selected) = max(states.items(), key=lambda item: (round(item[1][0], 12), item[0]))
    selections = [[SIGNS[i] for i in subset] for subset in selected]
    coverages = [sum(match["model"][OUTCOMES[i]] for i in subset) for match, subset in zip(matches, selected)]
    ratios = [sum(match["model"][OUTCOMES[i]] for i in subset) /
              max(sum(match["crowd"][OUTCOMES[i]] for i in subset), VALUE_FLOOR)
              for match, subset in zip(matches, selected)]
    mean_coverage = exp(sum(log(max(p, 1e-12)) for p in coverages) / len(matches))
    return {"budget": budget, "mode": mode, **system_cost(selections), "selections": selections,
            "objectiveScore": score, "metrics": {"coverageScore": mean_coverage,
            "allCorrectProbability": prod(coverages), "riskScore": 1 - mean_coverage,
            "valueIndex": exp(sum(log(max(r, 1e-12)) for r in ratios) / len(ratios))}}
