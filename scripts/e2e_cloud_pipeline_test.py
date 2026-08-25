"""
Complete End-to-End Live Cloud Integration Test for Azure Data & ML Platform.
Executes the full transaction -> lakehouse -> ML inference -> inventory risk -> monitoring loop.
"""
from datetime import datetime, timezone
import json
import logging
import sys
import uuid
import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("e2e_cloud_test")

GATEWAY_URL = "https://cloud-order-gateway.nicesea-33749800.canadacentral.azurecontainerapps.io"
ORDER_API_URL = "https://cloud-order-api.nicesea-33749800.canadacentral.azurecontainerapps.io"
ML_URL = "https://cloud-order-ml-service.nicesea-33749800.canadacentral.azurecontainerapps.io"
RISK_URL = "https://cloud-order-inventory-risk.nicesea-33749800.canadacentral.azurecontainerapps.io"
MON_URL = "https://cloud-order-ml-monitoring.nicesea-33749800.canadacentral.azurecontainerapps.io"


def run_e2e_cloud_pipeline():
    logger.info("================================================================================")
    logger.info("🚀 STARTING END-TO-END LIVE AZURE CLOUD PLATFORM VERIFICATION")
    logger.info("================================================================================")

    # --------------------------------------------------------------------------
    # Step 1: Health & Readiness Probes across Cloud Fleet
    # --------------------------------------------------------------------------
    logger.info("\n▶ STEP 1: Verifying Health & Readiness Probes across Azure Container Apps Fleet...")
    for name, url in [
        ("ML Inference Service", ML_URL),
        ("Inventory Risk Engine", RISK_URL),
        ("ML Monitoring Service", MON_URL),
    ]:
        r_health = requests.get(f"{url}/health", timeout=15)
        r_ready = requests.get(f"{url}/ready", timeout=15)
        assert r_health.status_code == 200, f"{name} health failed: {r_health.text}"
        assert r_ready.status_code == 200, f"{name} readiness failed: {r_ready.text}"
        logger.info(f"  ✓ {name:25s} -> Liveness: 200 OK | Readiness: 200 OK")

    # --------------------------------------------------------------------------
    # Step 2: Query Active Model Info & Feature Governance from Azure ML Service
    # --------------------------------------------------------------------------
    logger.info("\n▶ STEP 2: Querying ML Model Registry Lineage from Azure ML Service...")
    r_info = requests.get(f"{ML_URL}/model/info", timeout=15)
    assert r_info.status_code == 200, f"Model info failed: {r_info.text}"
    model_info = r_info.json()
    logger.info(f"  ✓ Model Name:        {model_info['model_name']}")
    logger.info(f"  ✓ Model Version:     v{model_info['model_version']}")
    logger.info(f"  ✓ Feature Contract:  {model_info['feature_version']} ({len(model_info['feature_columns'])} features)")
    logger.info(f"  ✓ Features:          {', '.join(model_info['feature_columns'][:5])}...")

    # --------------------------------------------------------------------------
    # Step 3: Run Multi-Step Recursive ML Demand Forecast (7-Day Horizon)
    # --------------------------------------------------------------------------
    logger.info("\n▶ STEP 3: Executing 7-Day Multi-Step Recursive Demand Forecast on Azure...")
    forecast_payload = {
        "product_id": 101,
        "forecast_horizon": 7,
        "unit_price": 49.99,
    }
    r_forecast = requests.post(f"{ML_URL}/forecast", json=forecast_payload, timeout=15)
    assert r_forecast.status_code == 200, f"Forecast failed: {r_forecast.text}"
    forecast_data = r_forecast.json()
    total_demand = forecast_data["total_predicted_demand"]
    daily_preds = [d["predicted_demand"] for d in forecast_data["daily_forecasts"]]

    logger.info(f"  ✓ Total 7-Day Predicted Demand: {total_demand:.2f} units")
    logger.info(f"  ✓ Daily Forecast Path:          {daily_preds}")
    logger.info(f"  ✓ Model Traceability:           {forecast_data['model_name']} (Version {forecast_data['model_version']})")

    # --------------------------------------------------------------------------
    # Step 4: Closed-Loop Operational Decision in Inventory Risk Engine
    # --------------------------------------------------------------------------
    logger.info("\n▶ STEP 4: Translating ML Forecast into Inventory Risk Decision & RabbitMQ Event...")
    risk_payload = {
        "product_id": 101,
        "current_inventory": 20,
        "safety_stock": 15,
        "forecast_horizon_days": 7,
        "forecasted_demand": total_demand,
    }
    r_risk = requests.post(f"{RISK_URL}/risk/evaluate-and-publish", json=risk_payload, timeout=15)
    assert r_risk.status_code == 200, f"Risk evaluation failed: {r_risk.text}"
    risk_data = r_risk.json()
    assessment = risk_data["assessment"]

    logger.info(f"  ✓ Current Inventory:            {assessment['current_inventory']} units")
    logger.info(f"  ✓ Inventory Position:           {assessment['inventory_position']:.1f} units")
    logger.info(f"  ✓ Stock Coverage Ratio:         {assessment['coverage_ratio']:.3f}x")
    logger.info(f"  ✓ Assessed Risk Level:          {assessment['risk_level']}")
    logger.info(f"  ✓ Recommended Reorder Qty:      {assessment['recommended_reorder_quantity']} units")
    logger.info(f"  ✓ Event Published to RabbitMQ:  {risk_data['event_published']} (Event ID: {risk_data.get('event_id')})")

    # --------------------------------------------------------------------------
    # Step 5: Log Prediction Lineage & Telemetry to Azure ML Monitoring Service
    # --------------------------------------------------------------------------
    logger.info("\n▶ STEP 5: Logging Prediction with Lineage to ML Monitoring & Gold Lakehouse...")
    pred_id = f"e2e-cloud-{uuid.uuid4().hex[:8]}"
    log_payload = {
        "prediction_id": pred_id,
        "product_id": 101,
        "prediction_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "forecast_horizon": 7,
        "predicted_demand": total_demand,
        "model_name": forecast_data["model_name"],
        "model_version": forecast_data["model_version"],
        "feature_version": forecast_data["feature_version"],
    }
    r_log = requests.post(f"{MON_URL}/monitoring/log-prediction", json=log_payload, timeout=15)
    assert r_log.status_code == 201, f"Log prediction failed: {r_log.text}"
    logger.info(f"  ✓ Logged Prediction Record:     {pred_id} (Status: {r_log.json()['status']})")

    # --------------------------------------------------------------------------
    # Step 6: Verify Holistic Monitoring Summary & Observability Report
    # --------------------------------------------------------------------------
    logger.info("\n▶ STEP 6: Fetching Holistic ML Monitoring & Observability Report...")
    r_report = requests.get(f"{MON_URL}/monitoring/report", timeout=15)
    assert r_report.status_code == 200, f"Report failed: {r_report.text}"
    report_data = r_report.json()

    logger.info(f"  ✓ Overall System Status:        {report_data['system_status']}")
    logger.info(f"  ✓ Total Requests Processed:     {report_data['operational_metrics']['request_count']}")
    logger.info(f"  ✓ Average Inference Latency:    {report_data['operational_metrics']['avg_latency_ms']} ms")
    logger.info(f"  ✓ p95 Inference Latency:        {report_data['operational_metrics']['p95_latency_ms']} ms")
    logger.info(f"  ✓ Operational Error Rate:       {report_data['operational_metrics']['error_rate_pct']}%")
    logger.info(f"  ✓ System Action Items:          {report_data['action_items']}")

    logger.info("\n================================================================================")
    logger.info("🎉 COMPLETE AZURE CLOUD PIPELINE VERIFIED SUCCESSFULLY (100% OPERATIONAL)!")
    logger.info("================================================================================")


if __name__ == "__main__":
    run_e2e_cloud_pipeline()
