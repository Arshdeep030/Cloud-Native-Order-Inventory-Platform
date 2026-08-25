"""
Automated Live Azure Container Apps Health & Integration Verification Script.
"""
import json
import logging
import sys
import requests

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("azure_verifier")

ML_URL = "https://cloud-order-ml-service.nicesea-33749800.canadacentral.azurecontainerapps.io"
RISK_URL = "https://cloud-order-inventory-risk.nicesea-33749800.canadacentral.azurecontainerapps.io"
MON_URL = "https://cloud-order-ml-monitoring.nicesea-33749800.canadacentral.azurecontainerapps.io"


def verify_azure_deployment():
    logger.info("================================================================")
    logger.info("🚀 EXECUTING AZURE CONTAINER APPS FLEET VERIFICATION")
    logger.info("================================================================")

    # 1. ML Service
    logger.info("\n--- [1] Azure ML Inference Service (Port 8004) ---")
    r_health = requests.get(f"{ML_URL}/health", timeout=15)
    assert r_health.status_code == 200
    logger.info(f"✓ GET /health: 200 OK -> {r_health.json()}")

    r_forecast = requests.post(
        f"{ML_URL}/forecast",
        json={"product_id": 1, "forecast_horizon": 7, "unit_price": 49.99},
        timeout=15,
    )
    assert r_forecast.status_code == 200
    forecast_data = r_forecast.json()
    logger.info(f"✓ POST /forecast (7-day): 200 OK -> Total Demand: {forecast_data['total_predicted_demand']}")

    # 2. Inventory Risk Service
    logger.info("\n--- [2] Azure Inventory Risk Engine (Port 8005) ---")
    r_risk_health = requests.get(f"{RISK_URL}/health", timeout=15)
    assert r_risk_health.status_code == 200
    logger.info(f"✓ GET /health: 200 OK -> {r_risk_health.json()}")

    r_risk_eval = requests.post(
        f"{RISK_URL}/risk/evaluate-and-publish",
        json={"product_id": 1, "current_inventory": 15, "safety_stock": 15, "forecast_horizon_days": 7},
        timeout=15,
    )
    assert r_risk_eval.status_code == 200
    risk_data = r_risk_eval.json()
    logger.info(f"✓ POST /risk/evaluate-and-publish: 200 OK -> Risk Level: {risk_data['assessment']['risk_level']}")
    logger.info(f"✓ Reorder Qty: {risk_data['assessment']['recommended_reorder_quantity']} | Event ID: {risk_data.get('event_id')}")

    # 3. ML Monitoring Service
    logger.info("\n--- [3] Azure ML Monitoring Service (Port 8006) ---")
    r_mon_health = requests.get(f"{MON_URL}/health", timeout=15)
    assert r_mon_health.status_code == 200
    logger.info(f"✓ GET /health: 200 OK -> {r_mon_health.json()}")

    r_log = requests.post(
        f"{MON_URL}/monitoring/log-prediction",
        json={
            "prediction_id": "azure-verification-run",
            "product_id": 1,
            "prediction_date": "2026-08-25",
            "forecast_horizon": 7,
            "predicted_demand": forecast_data["total_predicted_demand"],
            "model_name": forecast_data["model_name"],
            "model_version": forecast_data["model_version"],
            "feature_version": forecast_data["feature_version"],
        },
        timeout=15,
    )
    assert r_log.status_code == 201
    logger.info(f"✓ POST /monitoring/log-prediction: 201 Created -> {r_log.json()}")

    r_report = requests.get(f"{MON_URL}/monitoring/report", timeout=15)
    assert r_report.status_code == 200
    report_data = r_report.json()
    logger.info(f"✓ GET /monitoring/report: 200 OK -> System Status: {report_data['system_status']}")

    logger.info("\n================================================================")
    logger.info("🎉 LIVE CLOUD PLATFORM VERIFICATION SUCCESSFUL!")
    logger.info("================================================================")


if __name__ == "__main__":
    verify_azure_deployment()
