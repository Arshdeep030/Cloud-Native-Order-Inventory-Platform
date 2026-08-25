import numpy as np
import pandas as pd
import pytest

from ml.datasets.training_dataset import FEATURE_COLUMNS, TARGET_COLUMN
from ml.models.xgboost_model import DemandForecastingXGBoost
from ml.evaluation.model_gate import ModelAcceptanceGate


@pytest.fixture
def synthetic_test_df():
    np.random.seed(42)
    n = 30
    data = {
        "product_id": [1] * n,
        "date": [f"2026-08-{i:02d}" for i in range(1, n + 1)],
    }
    for col in FEATURE_COLUMNS:
        data[col] = np.random.uniform(10.0, 30.0, size=n)

    data[TARGET_COLUMN] = data["lag_1_demand"] * 0.7 + data["rolling_mean_7d"] * 0.3
    return pd.DataFrame(data)


def test_candidate_better_than_production_approved(synthetic_test_df):
    # Fit Production Model
    prod_model = DemandForecastingXGBoost(params={"n_estimators": 10, "max_depth": 2, "random_state": 42})
    prod_model.fit(synthetic_test_df)

    # Fit Candidate Model with higher capacity
    candidate_model = DemandForecastingXGBoost(params={"n_estimators": 50, "max_depth": 4, "random_state": 42})
    candidate_model.fit(synthetic_test_df)

    gate = ModelAcceptanceGate(regression_tolerance_pct=5.0)
    report = gate.evaluate_and_gate(
        candidate_model=candidate_model,
        test_df=synthetic_test_df,
        current_production_model=prod_model,
    )

    assert report.is_approved is True
    assert report.current_production_metrics is not None
    assert len(report.rejection_reasons) == 0


def test_candidate_worse_than_production_regression_rejected(synthetic_test_df):
    # Fit strong Production Model
    prod_model = DemandForecastingXGBoost(params={"n_estimators": 50, "max_depth": 4, "random_state": 42})
    prod_model.fit(synthetic_test_df)

    # Candidate with dummy underfitted parameters
    candidate_model = DemandForecastingXGBoost(params={"n_estimators": 1, "max_depth": 1, "learning_rate": 0.001, "random_state": 42})
    candidate_model.fit(synthetic_test_df)

    gate = ModelAcceptanceGate(regression_tolerance_pct=5.0)
    report = gate.evaluate_and_gate(
        candidate_model=candidate_model,
        test_df=synthetic_test_df,
        current_production_model=prod_model,
    )

    assert report.is_approved is False
    assert any("Model Regression" in r for r in report.rejection_reasons)
