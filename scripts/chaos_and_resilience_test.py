"""
Comprehensive Chaos & Failure Mode Resilience Verification Suite.
Validates fault tolerance across microservices, ML inference, Lakehouse, and Risk Engine.
"""
import logging
import math
import sys
import numpy as np
import pandas as pd

from inventory_risk.app.risk_engine import InventoryRiskEngine
from inventory_risk.app.publisher import RabbitMQRiskPublisher
from inventory_risk.app.schemas import RiskAssessmentRequest, RiskLevel
from ml.evaluation.model_gate import ModelAcceptanceGate
from ml.models.xgboost_model import DemandForecastingXGBoost
from ml.retraining.policy import RetrainingPolicy, TriggerType, TriggerSeverity
from ml_monitoring.app.drift_detector import calculate_psi, DriftDetector
from ml_monitoring.app.schemas import DriftStatus

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("chaos_resilience_test")


def run_chaos_and_resilience_tests():
    logger.info("================================================================================")
    logger.info("🛡️ EXECUTING PLATFORM CHAOS & FAILURE MODE RESILIENCE SUITE")
    logger.info("================================================================================")
    
    passed_tests = 0
    total_tests = 6

    # --------------------------------------------------------------------------
    # Scenario 1: ML Service Down Fallback in Inventory Risk Engine
    # --------------------------------------------------------------------------
    logger.info("\n--- [Scenario 1] ML Service Offline / Timeout Heuristic Fallback ---")
    offline_engine = InventoryRiskEngine(ml_service_url="http://invalid-unreachable-host:9999")
    
    # Assess product when ML endpoint is unreachable
    import asyncio
    req = RiskAssessmentRequest(product_id=99, current_inventory=5, safety_stock=15, forecast_horizon_days=7)
    res = asyncio.run(offline_engine.assess(req))
    
    assert res.risk_level in [RiskLevel.CRITICAL, RiskLevel.HIGH]
    assert res.recommended_reorder_quantity > 0
    logger.info(f"  ✓ Handled unreachable ML service gracefully. Fallback Risk: {res.risk_level.value}, Reorder: {res.recommended_reorder_quantity}")
    passed_tests += 1

    # --------------------------------------------------------------------------
    # Scenario 2: RabbitMQ Broker Disconnected Graceful Degradation
    # --------------------------------------------------------------------------
    logger.info("\n--- [Scenario 2] RabbitMQ Broker Unreachable / Network Partition ---")
    offline_publisher = RabbitMQRiskPublisher(rabbitmq_url="amqp://guest:guest@invalid-rabbitmq-host:9999/")
    event_id = offline_publisher.publish_risk_event(res)
    assert event_id is not None
    logger.info(f"  ✓ Gracefully caught broker outage. Emitted local fallback risk event: {event_id}")
    passed_tests += 1

    # --------------------------------------------------------------------------
    # Scenario 3: Zero Stock / Severe Stock-Out Extreme Boundary
    # --------------------------------------------------------------------------
    logger.info("\n--- [Scenario 3] Zero Physical Stock Critical Boundary Condition ---")
    zero_stock_res = offline_engine.calculate_risk(
        product_id=1,
        current_inventory=0,
        forecasted_demand=120.0,
        safety_stock=20,
    )
    assert zero_stock_res.risk_level == RiskLevel.CRITICAL
    assert zero_stock_res.coverage_ratio == 0.0
    assert zero_stock_res.recommended_reorder_quantity == 140
    logger.info(f"  ✓ Correctly escalated zero stock to CRITICAL risk (Reorder target: {zero_stock_res.recommended_reorder_quantity})")
    passed_tests += 1

    # --------------------------------------------------------------------------
    # Scenario 4: Model Regression Guard Rejection
    # --------------------------------------------------------------------------
    logger.info("\n--- [Scenario 4] Model Regression Protection (Inferior Candidate Rejection) ---")
    from ml.datasets.training_dataset import FEATURE_COLUMNS, TARGET_COLUMN
    np.random.seed(42)
    n = 40
    data = {"product_id": [1]*n, "date": [f"2026-08-{i:02d}" for i in range(1, n+1)]}
    for col in FEATURE_COLUMNS:
        data[col] = np.random.uniform(10.0, 30.0, size=n)
    data[TARGET_COLUMN] = data["lag_1_demand"] * 0.8 + data["rolling_mean_7d"] * 0.2
    test_df = pd.DataFrame(data)

    prod_model = DemandForecastingXGBoost(params={"n_estimators": 50, "max_depth": 3, "random_state": 42})
    prod_model.fit(test_df)

    underfit_candidate = DemandForecastingXGBoost(params={"n_estimators": 1, "max_depth": 1, "learning_rate": 0.0001, "random_state": 42})
    underfit_candidate.fit(test_df)

    gate = ModelAcceptanceGate(regression_tolerance_pct=5.0)
    approval_report = gate.evaluate_and_gate(
        candidate_model=underfit_candidate,
        test_df=test_df,
        current_production_model=prod_model,
    )
    assert approval_report.is_approved is False
    assert any("Model Regression" in r for r in approval_report.rejection_reasons)
    logger.info(f"  ✓ Acceptance Gate successfully blocked regressed model: {approval_report.rejection_reasons[0]}")
    passed_tests += 1

    # --------------------------------------------------------------------------
    # Scenario 5: Distribution Drift Spike (PSI >= 0.25 Alert)
    # --------------------------------------------------------------------------
    logger.info("\n--- [Scenario 5] Severe Feature Distribution Drift Detection ---")
    base_dist = np.random.normal(loc=20.0, scale=3.0, size=1000)
    drifted_dist = np.random.normal(loc=55.0, scale=8.0, size=1000)
    
    psi_score = calculate_psi(base_dist, drifted_dist)
    detector = DriftDetector(warning_threshold=0.10, critical_threshold=0.25)
    status = detector._classify_status(psi_score)
    
    assert psi_score >= 0.25
    assert status == DriftStatus.SIGNIFICANT_DRIFT
    logger.info(f"  ✓ Drift Engine detected distribution shift: PSI={psi_score:.3f} -> Status: {status.value}")
    passed_tests += 1

    # --------------------------------------------------------------------------
    # Scenario 6: Retraining Policy Priority Hierarchy
    # --------------------------------------------------------------------------
    logger.info("\n--- [Scenario 6] Retraining Policy Priority (Performance > Drift) ---")
    from ml_monitoring.app.schemas import ModelPerformanceMetric, PerformanceEvaluationReport
    policy = RetrainingPolicy(max_degradation_ratio=1.50)
    
    perf_report = PerformanceEvaluationReport(
        overall_performance=ModelPerformanceMetric(
            evaluated_samples=500,
            mae=4.80, # 4.80 / 1.68 = 2.85x degradation
            rmse=6.1,
            mape_pct=28.0,
            baseline_mae=1.68,
            degradation_ratio=2.85,
            status="DEGRADED",
            retraining_recommended=True,
        ),
        product_level_performance=[],
        retraining_recommended=True,
    )
    
    decision = policy.evaluate(performance_report=perf_report)
    assert decision.triggered is True
    assert decision.trigger_type == TriggerType.PERFORMANCE_DEGRADATION
    assert decision.severity == TriggerSeverity.CRITICAL
    logger.info(f"  ✓ Policy prioritizes Performance Degradation as CRITICAL severity ({decision.reasons[0]})")
    passed_tests += 1

    logger.info("\n================================================================================")
    logger.info(f"🎉 CHAOS & RESILIENCE SUITE PASSED: {passed_tests}/{total_tests} SCENARIOS VERIFIED!")
    logger.info("================================================================================")


if __name__ == "__main__":
    run_chaos_and_resilience_tests()
