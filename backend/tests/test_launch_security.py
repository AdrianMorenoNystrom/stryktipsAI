import json
from dataclasses import replace
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from app.services.explanations import explain
from app.services.probabilities import value_metrics


@pytest.mark.parametrize('model,crowd,selection,words',[
    ({'home':.6,'draw':.25,'away':.15},{'home':.8,'draw':.1,'away':.1},['1','X'],'överstreckat'),
    ({'home':.7,'draw':.2,'away':.1},{'home':.5,'draw':.3,'away':.2},['1'],'understreckat'),
    ({'home':.4,'draw':.3,'away':.3},{'home':.4,'draw':.3,'away':.3},['1','X','2'],'alla tre'),
    ({'home':.6,'draw':.25,'away':.15},{'home':.8,'draw':.15,'away':.05},['2'],'mindre sannolikt'),
])
def test_deterministic_explanations(model,crowd,selection,words):
    match={'model':model,'crowd':crowd,**value_metrics(model,crowd)}
    assert words in explain(match,selection)
    assert explain(match,selection)==explain(match,selection)
    assert 'garanterad' not in explain(match,selection)


def test_cors_and_production_shared_mutation_protection(monkeypatch):
    import app.main as main
    client=TestClient(main.app)
    allowed=client.options('/api/coupon/current',headers={'Origin':'http://localhost:4200','Access-Control-Request-Method':'GET'})
    assert allowed.headers['access-control-allow-origin']=='http://localhost:4200'
    denied=client.options('/api/coupon/current',headers={'Origin':'https://untrusted.invalid','Access-Control-Request-Method':'GET'})
    assert 'access-control-allow-origin' not in denied.headers
    monkeypatch.setattr(main,'runtime',replace(main.runtime,environment='production'))
    assert client.get('/api/coupon/demo').status_code==404
    assert client.post('/api/teams/aliases',json={'alias':'x','canonical':'Arsenal'}).status_code==403
    assert client.post('/api/coupon/current/refresh',headers={'Origin':'https://untrusted.invalid'}).status_code==403


def test_production_health_never_exposes_connection_errors(monkeypatch):
    import app.main as main
    def fail(**_):raise ValueError('secret connection content')
    monkeypatch.setattr(main,'DrawService',fail)
    response=TestClient(main.app).get('/health')
    assert response.status_code==503 and 'secret' not in response.text
