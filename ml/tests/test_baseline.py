import numpy as np
import pandas as pd
import pytest

from ml.baselines.demand_baseline import (
    calculate_metrics,
    NaiveDemandBaseline,
    MovingAverageDemandBaseline,
    BaselineEvaluator,
)


def test_calculate_metrics():
    y_true = np.array([10.0, 20.0, 30.0])
    y_pred = np.array([12.0, 18.0, 33.0])

    metrics = calculate_metrics(y_true, y_pred)
    assert round(metrics.mae, 2) == 2.33
    assert round(metrics.rmse, 2) == 2.38
    assert metrics.mape > 0.0



def test_baseline_evaluator():
    df = pd.DataFrame({
        "product_id": [1, 1, 1],
        "date": ["2026-08-01", "2026-08-02", "2026-08-03"],
        "lag_1_demand": [10.0, 15.0, 20.0],
        "rolling_mean_7d": [9.0, 14.0, 19.0],
        "demand_target": [12.0, 16.0, 22.0],
    })

    evaluator = BaselineEvaluator(target_column="demand_target")
    results = evaluator.evaluate_split("test_split", df)

    assert "Naive_Baseline" in results
    assert "7Day_Moving_Average" in results
    assert "MAE" in results["Naive_Baseline"]
    assert "RMSE" in results["Naive_Baseline"]
    assert "MAPE_pct" in results["Naive_Baseline"]
