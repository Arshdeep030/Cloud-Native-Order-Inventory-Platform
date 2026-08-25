import pytest
from fastapi.testclient import TestClient

from inventory_risk.app.main import app
from inventory_risk.app.schemas import RiskLevel


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "inventory-risk-service"


def test_post_risk_assess(client):
    payload = {
        "product_id": 101,
        "current_inventory": 20,
        "safety_stock": 15,
        "forecast_horizon_days": 7,
        "forecasted_demand": 85.0,
    }
    response = client.post("/risk/assess", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["product_id"] == 101
    assert data["current_inventory"] == 20
    assert data["forecasted_demand"] == 85.0
    assert data["risk_level"] == "CRITICAL"
    assert data["recommended_reorder_quantity"] == 80


def test_evaluate_and_publish_high_risk(client):
    # High risk -> event_published = True
    payload = {
        "product_id": 101,
        "current_inventory": 20,
        "safety_stock": 15,
        "forecast_horizon_days": 7,
        "forecasted_demand": 85.0,
    }
    response = client.post("/risk/evaluate-and-publish", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["event_published"] is True
    assert data["event_id"] is not None
    assert data["routing_key"] == "inventory.risk.detected"
    assert data["assessment"]["risk_level"] == "CRITICAL"


def test_evaluate_and_publish_low_risk(client):
    # Low risk -> event_published = False (no alert needed)
    payload = {
        "product_id": 103,
        "current_inventory": 200,
        "safety_stock": 15,
        "forecast_horizon_days": 7,
        "forecasted_demand": 30.0,
    }
    response = client.post("/risk/evaluate-and-publish", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["event_published"] is False
    assert data["assessment"]["risk_level"] == "LOW"


def test_get_product_risk_quick(client):
    response = client.get("/risk/products/1?current_inventory=25&forecast=80.0")
    assert response.status_code == 200
    data = response.json()
    assert data["product_id"] == 1
    assert data["risk_level"] in ["CRITICAL", "HIGH"]
