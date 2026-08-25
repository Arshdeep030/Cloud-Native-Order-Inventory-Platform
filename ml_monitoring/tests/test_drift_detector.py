import numpy as np
import pandas as pd
import pytest

from ml_monitoring.app.drift_detector import DriftDetector, calculate_psi
from ml_monitoring.app.schemas import DriftStatus


def test_calculate_psi_no_drift():
    # Identical distributions should yield PSI near 0.0 (< 0.05)
    np.random.seed(42)
    expected = np.random.normal(loc=20.0, scale=3.0, size=500)
    actual = np.random.normal(loc=20.0, scale=3.0, size=500)

    psi = calculate_psi(expected, actual)
    assert psi < 0.10


def test_calculate_psi_significant_drift():
    # Significant distribution shift (mean shifted from 20 to 45)
    np.random.seed(42)
    expected = np.random.normal(loc=20.0, scale=3.0, size=500)
    actual = np.random.normal(loc=45.0, scale=3.0, size=500)

    psi = calculate_psi(expected, actual)
    assert psi >= 0.25  # Significant drift


def test_drift_detector_assessment():
    detector = DriftDetector(warning_threshold=0.10, critical_threshold=0.25)

    base_df = pd.DataFrame({
        "lag_1_demand": np.random.normal(20, 2, 200),
        "rolling_mean_7d": np.random.normal(20, 2, 200),
    })

    # Shifted production data
    prod_df = pd.DataFrame({
        "lag_1_demand": np.random.normal(35, 2, 200),  # Drifted
        "rolling_mean_7d": np.random.normal(20, 2, 200),  # Not drifted
    })

    base_preds = np.random.normal(20, 2, 200)
    prod_preds = np.random.normal(35, 2, 200)  # Drifted

    report = detector.assess_drift(
        baseline_df=base_df,
        production_df=prod_df,
        feature_columns=["lag_1_demand", "rolling_mean_7d"],
        baseline_predictions=base_preds,
        production_predictions=prod_preds,
    )

    assert report.overall_status == DriftStatus.SIGNIFICANT_DRIFT
    assert report.retraining_recommended is True
    assert len(report.feature_drifts) == 2
