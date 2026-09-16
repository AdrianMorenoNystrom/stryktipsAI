"""Exercise a running backend and persist reviewable, actual verification results."""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import httpx
from app.config import ARTIFACTS, BUDGET_PRESETS, DATA


def verify(base_url: str) -> dict:
    with httpx.Client(base_url=base_url, timeout=60) as client:
        status = client.get("/api/model/status")
        status.raise_for_status()
        metadata = status.json()["metadata"]
        if metadata is None:
            raise RuntimeError("ML model is required for final MVP verification")
        coupon = client.get("/api/coupon/demo").json()
        systems = []
        example = None
        for mode in ("optimal", "safe", "value"):
            for budget in BUDGET_PRESETS:
                response = client.post("/api/coupon/optimize", json={"coupon": coupon, "mode": mode, "budget": budget})
                response.raise_for_status()
                result = response.json()
                system = result["system"]
                assert system["cost"] <= budget
                assert len(system["selections"]) == 13
                assert all(m["source"] in ("ml", "market_baseline") for m in result["matches"])
                if metadata.get("activeModel") == "market":
                    assert all(m["model"] == m["market"] for m in result["matches"])
                assert all(abs(sum(m["model"].values()) - 1) < 1e-9 for m in result["matches"])
                systems.append(system)
                if mode == "optimal" and budget == 256:
                    example = result
        report = {"verified_at": datetime.now(timezone.utc).isoformat(), "dataset": metadata["dataset_leagues"],
                  "dataset_total": metadata["dataset_matches"], "training_matches": metadata["training_matches"],
                  "feature_count": len(metadata["features"]), "modelVersion": metadata.get("modelVersion", "1.0"),
                  "activeModel": metadata.get("activeModel", "v1"),
                  "evaluation": metadata.get("evaluation", metadata.get("test")),
                  "systems": systems, "demo": example,
                  "import_failures": json.loads((DATA / "download_report.json").read_text(encoding="utf-8"))["failed"]}
        ARTIFACTS.mkdir(exist_ok=True, parents=True)
        filename = "demo_verification_v2.json" if metadata.get("modelVersion") == "2.0" else "demo_verification.json"
        (ARTIFACTS / filename).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    result = verify(parser.parse_args().url)
    print(json.dumps({k: v for k, v in result.items() if k not in ("demo", "evaluation")}, indent=2))
