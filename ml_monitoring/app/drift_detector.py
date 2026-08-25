from datetime import datetime, timezone
import logging
from typing import List, Optional

import numpy as np
import pandas as pd

from ml_monitoring.app.config import settings
from ml_monitoring.app.schemas import (
    DriftAssessmentReport,
    DriftStatus,
    FeatureDriftResult,
)

logger = logging.getLogger("drift_detector")


def calculate_psi(
    expected: np.ndarray,
    actual: np.ndarray,
    num_bins: int = 10,
    epsilon: float = 1e-4,
) -> float:
    """
    Calculates the Population Stability Index (PSI) between an expected (baseline)
    distribution and an actual (production) distribution.

    PSI Formula:
      PSI = sum((Actual_% - Expected_%) * ln(Actual_% / Expected_%))
    """
    exp = np.array(expected, dtype=float).ravel()
    act = np.array(actual, dtype=float).ravel()

    # Drop NaNs
    exp = exp[~np.isnan(exp)]
    act = act[~np.isnan(act)]

    if len(exp) == 0 or len(act) == 0:
        return 0.0

    # Determine quantile bins based on expected baseline
    quantiles = np.linspace(0, 100, num_bins + 1)
    bin_edges = np.percentile(exp, quantiles)
    # Ensure strictly increasing edges
    bin_edges = np.unique(bin_edges)
    if len(bin_edges) < 2:
        bin_edges = np.array([np.min(exp) - 1.0, np.max(exp) + 1.0])

    bin_edges[0] = -np.inf
    bin_edges[-1] = np.inf

    # Calculate bin counts
    exp_counts, _ = np.histogram(exp, bins=bin_edges)
    act_counts, _ = np.histogram(act, bins=bin_edges)

    # Normalize to proportions
    exp_pct = (exp_counts / len(exp)) + epsilon
    act_pct = (act_counts / len(act)) + epsilon

    # Normalize again so sum equals 1
    exp_pct = exp_pct / np.sum(exp_pct)
    act_pct = act_pct / np.sum(act_pct)

    # PSI calculation
    psi_value = np.sum((act_pct - exp_pct) * np.log(act_pct / exp_pct))
    return float(max(0.0, psi_value))


class DriftDetector:
    """
    Monitors input feature drift and prediction output drift using PSI.
    """

    def __init__(
        self,
        warning_threshold: float = settings.psi_warning_threshold,
        critical_threshold: float = settings.psi_critical_threshold,
    ):
        self.warning_threshold = warning_threshold
        self.critical_threshold = critical_threshold

    def _classify_status(self, psi_score: float) -> DriftStatus:
        if psi_score < self.warning_threshold:
            return DriftStatus.NO_DRIFT
        elif psi_score < self.critical_threshold:
            return DriftStatus.MODERATE_DRIFT
        return DriftStatus.SIGNIFICANT_DRIFT

    def evaluate_feature_drift(
        self,
        baseline_df: pd.DataFrame,
        production_df: pd.DataFrame,
        feature_columns: List[str],
    ) -> List[FeatureDriftResult]:
        """Calculates PSI for all specified feature columns."""
        results = []
        for col in feature_columns:
            if col in baseline_df.columns and col in production_df.columns:
                psi = calculate_psi(
                    baseline_df[col].to_numpy(), production_df[col].to_numpy()
                )
                status = self._classify_status(psi)
                results.append(
                    FeatureDriftResult(
                        feature_name=col,
                        psi_score=round(psi, 4),
                        status=status,
                        sample_size_reference=len(baseline_df),
                        sample_size_production=len(production_df),
                    )
                )
        return results

    def evaluate_prediction_drift(
        self,
        baseline_predictions: np.ndarray,
        production_predictions: np.ndarray,
    ) -> FeatureDriftResult:
        """Calculates PSI for model output predictions."""
        psi = calculate_psi(baseline_predictions, production_predictions)
        status = self._classify_status(psi)
        return FeatureDriftResult(
            feature_name="predicted_demand_output",
            psi_score=round(psi, 4),
            status=status,
            sample_size_reference=len(baseline_predictions),
            sample_size_production=len(production_predictions),
        )

    def assess_drift(
        self,
        baseline_df: pd.DataFrame,
        production_df: pd.DataFrame,
        feature_columns: List[str],
        baseline_predictions: np.ndarray,
        production_predictions: np.ndarray,
    ) -> DriftAssessmentReport:
        """Runs full drift evaluation and compiles a structured assessment report."""
        feature_drifts = self.evaluate_feature_drift(
            baseline_df, production_df, feature_columns
        )
        pred_drift = self.evaluate_prediction_drift(
            baseline_predictions, production_predictions
        )

        all_psis = [f.psi_score for f in feature_drifts] + [pred_drift.psi_score]
        max_psi = max(all_psis) if all_psis else 0.0
        overall_status = self._classify_status(max_psi)

        # Trigger retraining recommendation if critical drift or multiple moderate drifts exist
        critical_count = sum(
            1 for f in feature_drifts if f.status == DriftStatus.SIGNIFICANT_DRIFT
        ) + (1 if pred_drift.status == DriftStatus.SIGNIFICANT_DRIFT else 0)

        moderate_count = sum(
            1 for f in feature_drifts if f.status == DriftStatus.MODERATE_DRIFT
        ) + (1 if pred_drift.status == DriftStatus.MODERATE_DRIFT else 0)

        retraining_recommended = critical_count > 0 or moderate_count >= 3

        logger.info(
            f"Drift Assessment Completed: Overall Status={overall_status.value}, "
            f"Max PSI={max_psi:.3f}, Retraining Recommended={retraining_recommended}"
        )

        return DriftAssessmentReport(
            evaluated_at=datetime.now(timezone.utc).isoformat(),
            overall_status=overall_status,
            max_psi_score=round(max_psi, 4),
            feature_drifts=feature_drifts,
            prediction_drift=pred_drift,
            retraining_recommended=retraining_recommended,
        )
