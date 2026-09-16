from fastapi.testclient import TestClient
from app.main import app
import pytest

client = TestClient(app)


@pytest.fixture(autouse=True)
def isolate_coupon_storage(tmp_path, monkeypatch):
    monkeypatch.setenv("STRYKTIPS_NEWS_DIR", str(tmp_path))
    monkeypatch.setenv("NEWS_PROVIDER", "")


def test_news_api_time_validation_local_write_and_manual_snapshots():
    status = client.get("/api/news/status").json()
    assert not status["configured"] and not status["newsAffectsProbabilities"]
    coupon = client.get("/api/coupon/demo").json()
    assert client.post("/api/news/update", json={"coupon":coupon}, headers={"Origin":"https://example.com"}).status_code == 403
    assert client.get("/api/matches/unknown/news?as_of=2026-09-01T12:00:00").status_code == 422
    assert client.get("/api/matches/unknown/news?as_of=2099-01-01T12:00:00Z").status_code == 422
    first = client.post("/api/coupon/analyze", json={"coupon":coupon}).json()
    coupon["matches"][0]["marketOdds"]["home"] = 1.81
    client.post("/api/coupon/analyze", json={"coupon":coupon}).raise_for_status()
    snapshots = client.get(f"/api/coupon/{coupon['id']}/snapshots").json()
    assert len(snapshots) == 2
    assert client.get("/api/coupon/manual/current").json()["matches"][0]["marketOdds"]["home"] == 1.81
    identifier = first["matches"][0]["matchId"]
    for suffix in ("signals", "sources"):
        assert client.get(f"/api/matches/{identifier}/news/{suffix}").json() == []


def test_demo_full_api_flow_and_all_budgets():
    coupon = client.get("/api/coupon/demo").json()
    assert coupon["demo"] and len(coupon["matches"]) == 13
    for budget in (64, 128, 256, 512):
        response = client.post("/api/coupon/analyze", json={"coupon": coupon, "budget": budget, "mode": "optimal"})
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["system"]["cost"] <= budget
        assert len(result["insights"]) == 3
        assert len(result["matches"]) == 13
        for match in result["matches"]:
            assert abs(sum(match["model"].values()) - 1) < 1e-9
        cost = client.post("/api/coupon/cost", json={"selections": result["system"]["selections"]}).json()
        assert cost["rowCount"] == result["system"]["rowCount"]


def test_validation_error_is_readable_and_missing_odds_rejected():
    coupon = client.get("/api/coupon/demo").json()
    coupon["matches"][0]["crowd"] = {"home": 80, "draw": 30, "away": 10}
    response = client.post("/api/coupon/analyze", json={"coupon": coupon})
    assert response.status_code == 422
    assert "100" in response.json()["errors"][0]["message"]
    del coupon["matches"][0]["marketOdds"]
    response = client.post("/api/coupon/analyze", json={"coupon": coupon})
    assert response.status_code == 422
    assert any("marketOdds" in error["field"] for error in response.json()["errors"])


def test_status_search_and_cost_validation():
    assert client.get("/api/model/status").status_code == 200
    assert client.get("/api/teams/search?q=Manchester%20Utd").status_code == 200
    assert client.post("/api/coupon/cost", json={"selections": [["1"]] * 12 + [[]]}).status_code == 422
