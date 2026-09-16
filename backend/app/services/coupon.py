from datetime import datetime, timezone
from app.config import OUTCOMES, SIGNS
from app.schemas import AnalyzeRequest
from app.services.optimizer import optimize
from app.services.probabilities import value_metrics
from ml.predict import PredictionService
from app.services.match_identity import match_id


def explanation(match: dict, selection: list[str]) -> str:
    from app.services.explanations import explain
    return explain(match,selection)


def insights(matches: list[dict]) -> list[dict]:
    outcomes = [{"number": m["number"], "homeTeam": m["homeTeam"], "awayTeam": m["awayTeam"], "sign": sign,
                 "model": m["model"][k], "crowd": m["crowd"][k], "edge": m["edge"][k], "value": m["value"][k]}
                for m in matches for k, sign in zip(OUTCOMES, SIGNS)]
    singles = [o for o in outcomes if matches[o["number"] - 1]["recommendation"] == [o["sign"]]]
    strong = max(singles or outcomes, key=lambda o: o["model"])
    best_value = max(outcomes, key=lambda o: o["value"])
    warning = min(outcomes, key=lambda o: o["edge"])
    return [{"title": "STARKASTE SPIKEN", "description":"Den mest sannolika spiken i systemet." if singles else "Systemet saknar spikar; detta är det mest sannolika tecknet.", **strong},
            {"title": "BÄSTA VÄRDET", "description":"Störst förhållande mellan vår sannolikhet och folkets streck.", **best_value},
            {"title": "MATCHEN ATT SE UPP MED", "description":"Här ligger folkets streck högst över vår sannolikhet.", **warning}]


def analyze(request: AnalyzeRequest, predictor: PredictionService) -> dict:
    matches = []
    for match in sorted(request.coupon.matches, key=lambda m: m.number):
        prediction = predictor.predict(match)
        crowd = match.crowd.normalized()
        matches.append({**match.model_dump(mode="json"), "matchId": match_id(match), **prediction, "crowd": crowd,
                        **value_metrics(prediction["model"], crowd)})
    system = optimize(matches, request.budget, request.mode)
    for match, selection in zip(matches, system["selections"]):
        match["recommendation"] = selection
        match["mostLikely"] = SIGNS[max(range(3), key=lambda i: match["model"][OUTCOMES[i]])]
        match["bestValue"] = SIGNS[max(range(3), key=lambda i: match["value"][OUTCOMES[i]])]
        match["explanation"] = explanation(match, selection)
    return {"couponId": request.coupon.id, "demo": request.coupon.demo, "matches": matches,
            "system": system, "insights": insights(matches), "analyzedAt": datetime.now(timezone.utc).isoformat()}
