import pytest
from datetime import datetime, timedelta, timezone

from ml.retraining.policy import RetrainingPolicy, TriggerType, TriggerSeverity
from ml_monitoring.app.schemas import (
    DriftAssessmentReport,
    DriftStatus,
    FeatureDriftResult,
    ModelPerformanceMetric,
    PerformanceEvaluationReport,
)


@pytest.fixture
def policy():
    return RetrainingPolicy(
        max_degradation_ratio=1.50,
        psi_critical_threshold=0.25,
        max_model_age_days=30,
    )


def test_policy_no_triggers(policy):
    perf_report = PerformanceEvaluationReport(
        overall_performance=ModelPerformanceMetric(
            evaluated_samples=100,
            mae=1.50,
            rmse=2.0,
            mape_pct=10.0,
            baseline_mae=1.68,
            degradation_ratio=0.89,
            status="HEALTHY",
            retraining_recommended=False,
        ),
        product_level_performance=[],
        retraining_recommended=False,
    )

    decision = policy.evaluate(performance_report=perf_report)
    assert decision.triggered is False
    assert decision.trigger_type == TriggerType.NONE
    assert decision.severity == TriggerSeverity.NONE


def test_policy_performance_degradation_critical(policy):
    perf_report = PerformanceEvaluationReport(
        overall_performance=ModelPerformanceMetric(
            evaluated_samples=100,
            mae=3.50,  # 3.50 / 1.68 = 2.08x (> 1.50x)
            rmse=4.5,
            mape_pct=25.0,
            baseline_mae=1.68,
            degradation_ratio=2.08,
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
    assert "exceeding threshold" in decision.reasons[0]


def test_policy_drift_warning(policy):
    drift_report = DriftAssessmentReport(
        overall_status=DriftStatus.SIGNIFICANT_DRIFT,
        max_psi_score=0.32,
        feature_drifts=[],
        prediction_drift=FeatureDriftResult(
            feature_name="prediction",
            psi_score=0.32,
            status=DriftStatus.SIGNIFICANT_DRIFT,
            sample_size_reference=100,
            sample_size_production=100,
        ),
        retraining_recommended=True,
    )

    decision = policy.evaluate(drift_report=drift_report)
    assert decision.triggered is True
    assert decision.trigger_type == TriggerType.FEATURE_OR_PREDICTION_DRIFT
    assert decision.severity == TriggerSeverity.WARNING


def test_policy_scheduled_cadence(policy):
    old_date = (datetime.now(timezone.utc) - timedelta(days=35)).isoformat()
    decision = policy.evaluate(last_trained_date=old_date)

    assert decision.triggered is True
    assert decision.trigger_type == TriggerType.SCHEDULED_CADENCE
    assert decision.severity == TriggerSeverity.WARNING
