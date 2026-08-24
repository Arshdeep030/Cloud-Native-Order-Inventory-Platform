import tempfile
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from ml.datasets.training_dataset import FEATURE_COLUMNS, TARGET_COLUMN
from ml.models.xgboost_model import DemandForecastingXGBoost


@pytest.fixture
def synthetic_train_val_dfs():
    np.random.seed(42)
    n = 60
    data = {
        "product_id": [1] * n,
        "date": [f"2026-08-{i:02d}" for i in range(1, n + 1)],
    }
    for col in FEATURE_COLUMNS:
        data[col] = np.random.uniform(5.0, 25.0, size=n)
    # Target correlated with lag_1_demand + rolling_mean_7d
    data[TARGET_COLUMN] = (
        data["lag_1_demand"] * 0.5 + data["rolling_mean_7d"] * 0.5 + np.random.normal(0, 1.0, size=n)
    )

    df = pd.DataFrame(data)
    train_df = df.iloc[:40].copy()
    val_df = df.iloc[40:].copy()
    return train_df, val_df


def test_xgboost_fit_and_predict(synthetic_train_val_dfs):
    train_df, val_df = synthetic_train_val_dfs
    model = DemandForecastingXGBoost()
    model.fit(train_df, eval_df=val_df)

    assert model.is_fitted

    preds = model.predict(val_df)
    assert len(preds) == len(val_df)
    assert np.all(preds >= 0.0)  # No negative predictions

    importances = model.get_feature_importances()
    assert len(importances) == len(FEATURE_COLUMNS)
    assert sum(importances.values()) > 0.0


def test_xgboost_save_and_load(synthetic_train_val_dfs):
    train_df, val_df = synthetic_train_val_dfs
    model = DemandForecastingXGBoost()
    model.fit(train_df)

    with tempfile.TemporaryDirectory() as tmp_dir:
        model_path = Path(tmp_dir) / "test_model.json"
        model.save_model(str(model_path))
        assert model_path.exists()

        new_model = DemandForecastingXGBoost()
        new_model.load_model(str(model_path))
        assert new_model.is_fitted

        orig_preds = model.predict(val_df)
        loaded_preds = new_model.predict(val_df)
        np.testing.assert_allclose(orig_preds, loaded_preds, rtol=1e-4)
