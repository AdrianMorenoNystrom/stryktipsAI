import logging
import math
import os
import json
from copy import deepcopy
from pathlib import Path
from threading import RLock

from app.config import ARTIFACTS, DATA, MIN_HISTORY, OUTCOMES
from app.schemas import MatchInput
from app.services.probabilities import devig
from app.services.teams import normalize_team, team_id
from app.config import season_label


def clean(value):
    if isinstance(value, dict):
        return {k: clean(v) for k, v in value.items()}
    if isinstance(value, list):
        return [clean(v) for v in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


class PredictionService:
    def __init__(self, artifact_dir: Path = ARTIFACTS) -> None:
        self.path = artifact_dir / "model.joblib"
        self.bundle = None
        self.signature = None
        self.error = None
        self.lock = RLock()

    def load(self) -> None:
        with self.lock:
            if not self.path.exists():
                self.bundle, self.signature = None, None
                if os.getenv('ENVIRONMENT') == 'production':
                    # Explicit portable deployment policy; no synthetic training/form.
                    metadata=json.loads((Path(__file__).resolve().parents[1]/'app'/'production_model_metadata.json').read_text(encoding='utf-8'))
                    self.bundle = {'metadata':metadata, 'state':None}
                return
            signature = (self.path.stat().st_mtime_ns, self.path.stat().st_size)
            if self.signature != signature:
                try:
                    import joblib
                    bundle = joblib.load(self.path)
                    if not {"model", "state", "metadata", "features"}.issubset(bundle):
                        raise ValueError("Invalid model artifact")
                    self.bundle, self.signature, self.error = bundle, signature, None
                except Exception:
                    logging.exception("Could not load model artifact")
                    self.bundle, self.error = None, "Modellfilen kunde inte läsas. Kör träningen igen."

    def status(self) -> dict:
        self.load()
        return {"trained": self.bundle is not None, "datasetAvailable": (DATA / "processed" / "matches.parquet").exists(),
                "error": self.error, "metadata": self.bundle["metadata"] if self.bundle else None}

    def predict(self, match: MatchInput) -> dict:
        self.load()
        market = devig(match.marketOdds.model_dump())
        response = {"model": market, "market": market, "source": "market_fallback", "warnings": [], "features": {},
                    "form": {"home": [], "away": []}}
        bundle = self.bundle
        if bundle is None:
            response["warnings"].append(self.error or "Modell saknas. Marknadsprognosen används tills historiken har tränats.")
            return response
        active_market = bundle["metadata"].get("activeModel") == "market"
        response["activeModel"] = bundle["metadata"].get("activeModelLabel", "Model v1")
        response["modelVersion"] = bundle["metadata"].get("modelVersion", "1.0")
        response["newsAffectsProbabilities"] = False
        if active_market:
            response["source"] = "market_baseline"
        if match.league not in ("E0", "E1", "E2"):
            response["source"] = "market_fallback"
            response["warnings"].append("No trained league coverage. Dokumenterad fallback: normaliserade inversa observerade odds; ingen tränad ligakorrektion.")
            return response
        if bundle['state'] is None:
            return response
        import pandas as pd
        if pd.Timestamp(match.date) <= pd.Timestamp(bundle["metadata"]["data_through"]):
            response["warnings"].append("Matchdatum ligger inom modellens träningshistorik. Marknadsprognosen används för att undvika framtidsläckage.")
            return response
        state = bundle["state"]
        unknown = [normalize_team(name) for name in (match.homeTeam, match.awayTeam)
                   if team_id(name) not in state.teams or state.teams[team_id(name)].total < MIN_HISTORY]
        if unknown:
            response["warnings"].append(f"Otillräcklig historik för {', '.join(unknown)}. Marknadsprognosen används som fallback.")
            return response
        row = {"home_team_id": team_id(match.homeTeam), "away_team_id": team_id(match.awayTeam),
               "date": match.date, "league": match.league, "season": season_label(match.date.year if match.date.month >= 7 else match.date.year - 1),
               **{f"market_prob_{k}": v for k, v in market.items()}}
        if getattr(state, "season_regression", 1.0) != 1.0 or getattr(state, "division_adjustment", 0.0):
            state = deepcopy(state)
            state.begin_day([row])
        features = state.features(row)
        response["features"] = clean(features)
        response["form"] = {side: clean(list(state.teams[row[f"{side}_team_id"]].history)[-5:]) for side in ("home", "away")}
        if active_market:
            return response
        try:
            probabilities = bundle["model"].predict_proba(pd.DataFrame([features])[bundle["features"]])[0]
            if not all(math.isfinite(float(p)) and p >= 0 for p in probabilities):
                raise ValueError("Invalid probabilities")
            response["model"] = {k: float(v) for k, v in zip(OUTCOMES, probabilities)}
            response["source"] = "ml"
        except Exception:
            logging.exception("Prediction failed")
            response["warnings"].append("Modellprognosen misslyckades. Marknadsprognosen används som fallback.")
        return response
