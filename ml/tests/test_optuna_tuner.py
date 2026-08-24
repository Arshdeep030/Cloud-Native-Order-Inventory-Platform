import numpy as np
import pandas as pd
import pytest

from ml.datasets.training_dataset import FEATURE_COLUMNS, TARGET_COLUMN
from ml.tuning.optuna_tuner import OptunaHyperparameterTuner


@pytest.fixture
def tuning_data():
    np.random.seed(42)
    n = 60
    data = {
        "product_id": [1] * n,
        "date": [f"2026-08-{i:02d}" for i in range(1, n + 1)],
    }
    for col in FEATURE_COLUMNS:
        data[col] = np.random.uniform(5.0, 20.0, size=n)
    data[TARGET_COLUMN] = data["lag_1_demand"] * 0.8 + 2.0

    df = pd.DataFrame(data)
    train_df = df.iloc[:40].copy()
    val_df = df.iloc[40:].copy()
    return train_df, val_df


def test_optuna_hyperparameter_tuner(tuning_data):
    train_df, val_df = tuning_data
    tuner = OptunaHyperparameterTuner(n_trials=5, random_seed=42)
    result = tuner.tune(train_df, val_df)

    assert result.n_trials == 5
    assert "n_estimators" in result.best_params
    assert "max_depth" in result.best_params
    assert result.best_val_mae >= 0.0
    assert result.best_model.is_fitted
