import pytest
from fastapi.testclient import TestClient

from ml_monitoring.app.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "ml-monitoring-service"


def test_log_prediction_endpoint(client):
    payload = {
        "prediction_id": "test-api-pred-1",
        "product_id": 1,
        "prediction_date": "2026-08-25",
        "forecast_horizon": 7,
        "predicted_demand": 24.5,
        "model_name": "demand_forecasting_xgboost",
        "model_version": "1",
        "feature_version": "v1",
    }
    response = client.post("/monitoring/log-prediction", json=payload)
    assert response.status_code == 201
    assert response.json()["status"] == "LOGGED"


def test_get_metrics_endpoint(client):
    response = client.get("/monitoring/metrics")
    assert response.status_code == 200
    data = response.json()
    assert "request_count" in data
    assert "avg_latency_ms" in data


def test_get_report_endpoint(client):
    response = client.get("/monitoring/report")
    assert response.status_code == 200
    data = response.json()
    assert data["system_status"] in ["HEALTHY", "WARNING", "CRITICAL"]
    assert "operational_metrics" in data
    assert "action_items" in data
