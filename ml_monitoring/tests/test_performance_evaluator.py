import tempfile
from pathlib import Path
import pandas as pd
import pytest

from ml_monitoring.app.performance_evaluator import PerformanceEvaluator


@pytest.fixture
def evaluator():
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield PerformanceEvaluator(
            baseline_acceptance_mae=2.0,
            max_degradation_ratio=1.5,
            output_path=str(Path(tmp_dir) / "performance"),
        )


def test_performance_evaluator_healthy(evaluator):
    preds_df = pd.DataFrame({
        "product_id": [1, 1, 2, 2],
        "prediction_date": ["2026-08-25", "2026-08-26", "2026-08-25", "2026-08-26"],
        "predicted_demand": [20.0, 22.0, 15.0, 17.0],
    })

    actuals_df = pd.DataFrame({
        "product_id": [1, 1, 2, 2],
        "date": ["2026-08-25", "2026-08-26", "2026-08-25", "2026-08-26"],
        "actual_demand": [21.0, 23.0, 14.0, 16.0],  # Error is 1.0
    })

    report = evaluator.evaluate(preds_df, actuals_df)

    assert report.overall_performance.evaluated_samples == 4
    assert report.overall_performance.mae == 1.0
    assert report.overall_performance.status == "HEALTHY"
    assert report.retraining_recommended is False
    assert len(report.product_level_performance) == 2


def test_performance_evaluator_degraded(evaluator):
    # Predictions far from actuals -> high MAE
    preds_df = pd.DataFrame({
        "product_id": [1, 1],
        "date": ["2026-08-25", "2026-08-26"],
        "predicted_demand": [10.0, 10.0],
    })

    actuals_df = pd.DataFrame({
        "product_id": [1, 1],
        "date": ["2026-08-25", "2026-08-26"],
        "actual_demand": [20.0, 20.0],  # Error is 10.0 (baseline is 2.0 -> ratio 5.0x)
    })

    report = evaluator.evaluate(preds_df, actuals_df)

    assert report.overall_performance.mae == 10.0
    assert report.overall_performance.status == "DEGRADED"
    assert report.retraining_recommended is True
