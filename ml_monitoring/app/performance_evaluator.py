from datetime import datetime, timezone
import json
import logging
from pathlib import Path
from typing import List, Optional

import numpy as np
import pandas as pd

from ml_monitoring.app.config import settings
from ml_monitoring.app.schemas import (
    ModelPerformanceMetric,
    PerformanceEvaluationReport,
)

logger = logging.getLogger("performance_evaluator")


class PerformanceEvaluator:
    """
    Evaluates actual-vs-predicted performance over time when ground-truth actual
    demand arrives, monitoring MAE, RMSE, and MAPE degradation vs baseline.
    """

    def __init__(
        self,
        baseline_acceptance_mae: float = settings.baseline_acceptance_mae,
        max_degradation_ratio: float = settings.max_acceptable_degradation_ratio,
        output_path: str = settings.performance_logs_path,
    ):
        self.baseline_acceptance_mae = baseline_acceptance_mae
        self.max_degradation_ratio = max_degradation_ratio
        self.output_path = Path(output_path)

    def evaluate(
        self,
        predictions_df: pd.DataFrame,
        actuals_df: pd.DataFrame,
    ) -> PerformanceEvaluationReport:
        """
        Joins predictions and actuals on (product_id, date) and calculates
        overall and per-product performance metrics.
        """
        # Harmonize column names
        preds = predictions_df.copy()
        acts = actuals_df.copy()

        if "prediction_date" in preds.columns:
            preds["date"] = preds["prediction_date"].astype(str)
        else:
            preds["date"] = preds["date"].astype(str)

        acts["date"] = acts["date"].astype(str)

        merged = pd.merge(
            preds,
            acts,
            on=["product_id", "date"],
            how="inner",
            suffixes=("_pred", "_act"),
        )

        if len(merged) == 0:
            raise ValueError(
                "No overlapping (product_id, date) records found between predictions and actuals."
            )

        # 1. Overall Performance
        y_act = merged["actual_demand"].to_numpy(dtype=float)
        y_pred = merged["predicted_demand"].to_numpy(dtype=float)

        overall_mae = float(np.mean(np.abs(y_act - y_pred)))
        overall_rmse = float(np.sqrt(np.mean((y_act - y_pred) ** 2)))
        overall_mape = float(
            np.mean(np.abs(y_act - y_pred) / np.maximum(y_act, 0.01)) * 100.0
        )
        overall_deg_ratio = overall_mae / max(self.baseline_acceptance_mae, 0.01)
        overall_retrain = overall_deg_ratio > self.max_degradation_ratio

        overall_metric = ModelPerformanceMetric(
            product_id=None,
            evaluated_samples=len(merged),
            mae=round(overall_mae, 3),
            rmse=round(overall_rmse, 3),
            mape_pct=round(overall_mape, 2),
            baseline_mae=round(self.baseline_acceptance_mae, 3),
            degradation_ratio=round(overall_deg_ratio, 2),
            status="DEGRADED" if overall_retrain else "HEALTHY",
            retraining_recommended=overall_retrain,
        )

        # 2. Product-level breakdown
        product_metrics: List[ModelPerformanceMetric] = []
        for p_id, group in merged.groupby("product_id"):
            g_act = group["actual_demand"].to_numpy(dtype=float)
            g_pred = group["predicted_demand"].to_numpy(dtype=float)

            p_mae = float(np.mean(np.abs(g_act - g_pred)))
            p_rmse = float(np.sqrt(np.mean((g_act - g_pred) ** 2)))
            p_mape = float(
                np.mean(np.abs(g_act - g_pred) / np.maximum(g_act, 0.01)) * 100.0
            )
            p_deg = p_mae / max(self.baseline_acceptance_mae, 0.01)
            p_retrain = p_deg > self.max_degradation_ratio

            product_metrics.append(
                ModelPerformanceMetric(
                    product_id=int(p_id),
                    evaluated_samples=len(group),
                    mae=round(p_mae, 3),
                    rmse=round(p_rmse, 3),
                    mape_pct=round(p_mape, 2),
                    baseline_mae=round(self.baseline_acceptance_mae, 3),
                    degradation_ratio=round(p_deg, 2),
                    status="DEGRADED" if p_retrain else "HEALTHY",
                    retraining_recommended=p_retrain,
                )
            )

        report = PerformanceEvaluationReport(
            evaluated_at=datetime.now(timezone.utc).isoformat(),
            overall_performance=overall_metric,
            product_level_performance=product_metrics,
            retraining_recommended=overall_retrain,
        )

        # 3. Save report to Gold lakehouse storage
        now = datetime.now(timezone.utc)
        target_dir = (
            self.output_path
            / f"year={now.year:04d}"
            / f"month={now.month:02d}"
        )
        target_dir.mkdir(parents=True, exist_ok=True)
        report_file = target_dir / "performance_evaluations.jsonl"
        with open(report_file, "a", encoding="utf-8") as f:
            f.write(report.model_dump_json() + "\n")

        logger.info(
            f"Performance Evaluation Completed ({len(merged)} samples): MAE={overall_mae:.2f} "
            f"(Degradation Ratio={overall_deg_ratio:.2f}x vs Baseline), Status={overall_metric.status}"
        )

        return report
