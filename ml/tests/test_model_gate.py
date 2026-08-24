import numpy as np
import pandas as pd
import pytest

from ml.datasets.training_dataset import FEATURE_COLUMNS, TARGET_COLUMN
from ml.models.xgboost_model import DemandForecastingXGBoost
from ml.evaluation.model_gate import ModelAcceptanceGate


@pytest.fixture
def test_dataset_and_models():
    np.random.seed(42)
    n = 30
    data = {
        "product_id": [1] * n,
        "date": [f"2026-08-{i:02d}" for i in range(1, n + 1)],
    }
    for col in FEATURE_COLUMNS:
        data[col] = np.random.uniform(10.0, 30.0, size=n)

    # Strong linear pattern
    data[TARGET_COLUMN] = (
        data["lag_1_demand"] * 0.7 + data["rolling_mean_7d"] * 0.3
    )

    test_df = pd.DataFrame(data)

    # Train a strong model
    model = DemandForecastingXGBoost()
    model.fit(test_df)

    return model, test_df


def test_model_acceptance_gate_approved(test_dataset_and_models):
    model, test_df = test_dataset_and_models
    gate = ModelAcceptanceGate(max_acceptable_mape=35.0)
    report = gate.evaluate_and_gate(model, test_df)

    assert report.test_samples == len(test_df)
    assert report.is_approved
    assert report.candidate_metrics["MAE"] < report.baseline_metrics[report.strongest_baseline]["MAE"]
    assert len(report.rejection_reasons) == 0


def test_model_acceptance_gate_rejected():
    # Test rejection when max_acceptable_mape threshold is unrealistically strict
    np.random.seed(42)
    n = 20
    data = {
        "product_id": [1] * n,
        "date": [f"2026-08-{i:02d}" for i in range(1, n + 1)],
    }
    for col in FEATURE_COLUMNS:
        data[col] = np.random.uniform(5.0, 15.0, size=n)
    data[TARGET_COLUMN] = np.random.uniform(50.0, 100.0, size=n)

    test_df = pd.DataFrame(data)
    model = DemandForecastingXGBoost()
    model.fit(test_df)

    gate = ModelAcceptanceGate(max_acceptable_mape=0.01)  # Impossibly strict
    report = gate.evaluate_and_gate(model, test_df)

    assert not report.is_approved
    assert len(report.rejection_reasons) > 0
