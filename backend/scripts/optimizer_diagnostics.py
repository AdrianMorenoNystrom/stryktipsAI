"""Diagnostic synthetic crowd scenarios on held-out historical matches, not payout backtests."""
from collections import Counter
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd
from app.config import ARTIFACTS, BUDGET_PRESETS, OUTCOMES, SEED
from app.services.optimizer import optimize


def run_diagnostics() -> dict:
    predictions = pd.read_parquet(ARTIFACTS / "walk_forward_predictions.parquet").sort_values(["date", "match_id"])
    # Adjacent dated test matches create plausible 13-match samples without reusing outcomes in optimization.
    coupons = [predictions.iloc[start:start + 13] for start in range(0, len(predictions) - 12, 13)]
    scenarios = {"market_like": 1.0, "favourite_biased": 1.3, "longshot_biased": .8}
    output = []
    for scenario, exponent in scenarios.items():
        for mode in ("optimal", "safe", "value"):
            for budget in BUDGET_PRESETS:
                combinations = Counter()
                totals = Counter()
                draw_probability, draw_coverage = 0.0, 0
                for coupon in coupons:
                    market = coupon[[f"market_{i}" for i in range(3)]].to_numpy()
                    model = coupon[[f"active_{i}" for i in range(3)]].to_numpy()
                    crowd = market ** exponent
                    crowd /= crowd.sum(axis=1, keepdims=True)
                    matches = [{"model": dict(zip(OUTCOMES, p)), "crowd": dict(zip(OUTCOMES, q))} for p, q in zip(model, crowd)]
                    system = optimize(matches, budget, mode)
                    assert system["cost"] <= budget
                    for selection in system["selections"]:
                        combinations["".join(selection)] += 1
                        draw_coverage += int("X" in selection)
                    for name in ("singles", "doubles", "triples", "cost"):
                        totals[name] += system[name]
                    draw_probability += model[:, 1].sum()
                n = len(coupons)
                doubles = sum(combinations[k] for k in ("1X", "12", "X2"))
                output.append({"scenario": scenario, "mode": mode, "budget": budget, "coupons": n,
                    "average_singles": totals["singles"] / n, "average_doubles": totals["doubles"] / n,
                    "average_triples": totals["triples"] / n, "budget_utilization": totals["cost"] / (n * budget),
                    "combinations": {s: combinations[s] for s in ("1", "X", "2", "1X", "12", "X2", "1X2")},
                    "double_distribution": {s: combinations[s] / doubles if doubles else 0 for s in ("1X", "12", "X2")},
                    "draw_coverage_fraction": draw_coverage / (n * 13), "mean_draw_probability": draw_probability / (n * 13)})
                print(f"{scenario} {mode} {budget}: {n} coupons", flush=True)
    report = {"seed": SEED, "coupon_construction": "Non-overlapping chronological blocks of 13 out-of-sample matches; fixtures may span several dates.",
              "crowd_is_simulated": True, "crowd_formula": "normalize(market ** exponent)", "scenario_exponents": scenarios,
              "objective_changed": False, "total_coupons_per_scenario": len(coupons), "results": output,
              "explanation": "The objective rewards covered probability and crowd-relative value, not equal counts of each sign. When home and away probabilities exceed draw, 12 can be the best double. Synthetic crowd exponents change this preference. This is not evidence of an objective bug or a payout advantage."}
    (ARTIFACTS / "optimizer_diagnostics.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    run_diagnostics()
