import pytest
from fastapi.testclient import TestClient

from ml_service.app.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "ml-inference-service"


def test_readiness_endpoint(client):
    response = client.get("/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["model_loaded"] is True

    assert "timestamp" in data


def test_model_info_endpoint(client):
    response = client.get("/model/info")
    assert response.status_code == 200
    data = response.json()
    assert data["model_name"] == "demand_forecasting_xgboost"
    assert data["model_version"] == "1"
    assert data["feature_version"] == "v1"
    assert "lag_1_demand" in data["feature_columns"]
    assert data["is_loaded"] is True


def test_post_forecast_endpoint(client):
    payload = {
        "product_id": 1,
        "forecast_horizon": 7,
        "recent_demand_history": [12.0, 14.0, 15.0, 16.0, 18.0, 20.0, 22.0] * 2,
        "unit_price": 199.99,
        "start_date": "2026-08-25",
    }
    response = client.post("/forecast", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["product_id"] == 1
    assert data["model_version"] == "1"
    assert data["forecast_horizon"] == 7
    assert len(data["daily_forecasts"]) == 7
    assert data["total_predicted_demand"] > 0.0


def test_get_forecast_endpoint(client):
    response = client.get("/forecast/2?days=5&unit_price=49.99")
    assert response.status_code == 200
    data = response.json()
    assert data["product_id"] == 2
    assert data["forecast_horizon"] == 5
    assert len(data["daily_forecasts"]) == 5
