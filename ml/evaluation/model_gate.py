from dataclasses import dataclass
from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional

import pandas as pd

from ml.baselines.demand_baseline import (
    BaselineEvaluator,
    calculate_metrics,
    ForecastMetrics,
)
from ml.datasets.training_dataset import TARGET_COLUMN
from ml.models.xgboost_model import DemandForecastingXGBoost

logger = logging.getLogger("ml_model_gate")


@dataclass
class ModelApprovalReport:
    is_approved: bool
    evaluated_at: str
    test_samples: int
    candidate_metrics: Dict[str, float]
    baseline_metrics: Dict[str, Dict[str, float]]
    strongest_baseline: str
    mae_improvement_pct: float
    rmse_improvement_pct: float
    current_production_metrics: Optional[Dict[str, float]] = None
    improvement_vs_production_pct: Optional[float] = None
    rejection_reasons: List[str] = None

    def __post_init__(self):
        if self.rejection_reasons is None:
            self.rejection_reasons = []


class ModelAcceptanceGate:
    """
    Evaluates candidate models on the untouched Test partition against
    both baseline benchmark models AND the currently active production model.
    Enforces regression protection and deployment quality criteria.
    """

    def __init__(
        self,
        target_column: str = TARGET_COLUMN,
        max_acceptable_mape: float = 35.0,
        min_required_mae_improvement_pct: float = 0.0,
        regression_tolerance_pct: float = 5.0,  # candidate can't be >5% worse than current prod
    ):
        self.target_column = target_column
        self.max_acceptable_mape = max_acceptable_mape
        self.min_required_mae_improvement_pct = min_required_mae_improvement_pct
        self.regression_tolerance_pct = regression_tolerance_pct
        self.baseline_evaluator = BaselineEvaluator(target_column=target_column)

    def evaluate_and_gate(
        self,
        candidate_model: DemandForecastingXGBoost,
        test_df: pd.DataFrame,
        current_production_model: Optional[DemandForecastingXGBoost] = None,
    ) -> ModelApprovalReport:
        """
        Executes formal evaluation gate on Test set against baselines and current production.
        """
        if self.target_column not in test_df.columns:
            raise ValueError(f"Target column '{self.target_column}' missing in test dataset.")

        y_true = test_df[self.target_column].to_numpy()

        # 1. Candidate XGBoost Evaluation
        y_pred = candidate_model.predict(test_df)
        candidate_metrics = calculate_metrics(y_true, y_pred)

        # 2. Baseline Models Evaluation
        baseline_results = self.baseline_evaluator.evaluate_split("Test_Set", test_df)

        # 3. Determine Strongest Baseline
        naive_mae = baseline_results["Naive_Baseline"]["MAE"]
        ma_mae = baseline_results["7Day_Moving_Average"]["MAE"]
        naive_rmse = baseline_results["Naive_Baseline"]["RMSE"]
        ma_rmse = baseline_results["7Day_Moving_Average"]["RMSE"]

        if naive_mae <= ma_mae:
            strongest_baseline_name = "Naive_Baseline"
            best_base_mae = naive_mae
            best_base_rmse = naive_rmse
        else:
            strongest_baseline_name = "7Day_Moving_Average"
            best_base_mae = ma_mae
            best_base_rmse = ma_rmse

        # 4. Improvement Percentages vs Baseline
        mae_imp_pct = (
            ((best_base_mae - candidate_metrics.mae) / best_base_mae * 100.0)
            if best_base_mae > 0
            else 0.0
        )
        rmse_imp_pct = (
            ((best_base_rmse - candidate_metrics.rmse) / best_base_rmse * 100.0)
            if best_base_rmse > 0
            else 0.0
        )

        rejection_reasons = []

        # 5. Baseline Comparison Checks
        if candidate_metrics.mae >= best_base_mae:
            rejection_reasons.append(
                f"Candidate MAE ({candidate_metrics.mae:.2f}) failed to beat {strongest_baseline_name} MAE ({best_base_mae:.2f})"
            )

        if candidate_metrics.mape > self.max_acceptable_mape:
            rejection_reasons.append(
                f"Candidate MAPE ({candidate_metrics.mape:.1f}%) exceeds maximum threshold ({self.max_acceptable_mape:.1f}%)"
            )

        # 6. Current Production Model Regression Protection Check
        prod_metrics_dict: Optional[Dict[str, float]] = None
        imp_vs_prod_pct: Optional[float] = None

        if current_production_model is not None and current_production_model.is_fitted:
            y_prod_preds = current_production_model.predict(test_df)
            prod_metrics = calculate_metrics(y_true, y_prod_preds)
            prod_metrics_dict = prod_metrics.to_dict()

            if prod_metrics.mae > 0:
                imp_vs_prod_pct = round(
                    ((prod_metrics.mae - candidate_metrics.mae) / prod_metrics.mae * 100.0),
                    2,
                )
            else:
                imp_vs_prod_pct = 0.0

            # Regression Guard: reject if candidate MAE is worse than production MAE by more than tolerance
            max_allowed_mae = prod_metrics.mae * (1.0 + self.regression_tolerance_pct / 100.0)
            if candidate_metrics.mae > max_allowed_mae:
                rejection_reasons.append(
                    f"Model Regression: Candidate MAE ({candidate_metrics.mae:.2f}) is worse than "
                    f"current production model MAE ({prod_metrics.mae:.2f} + {self.regression_tolerance_pct}% tolerance)."
                )

        is_approved = len(rejection_reasons) == 0

        report = ModelApprovalReport(
            is_approved=is_approved,
            evaluated_at=datetime.now(timezone.utc).isoformat(),
            test_samples=len(test_df),
            candidate_metrics=candidate_metrics.to_dict(),
            baseline_metrics=baseline_results,
            strongest_baseline=strongest_baseline_name,
            mae_improvement_pct=round(mae_imp_pct, 2),
            rmse_improvement_pct=round(rmse_imp_pct, 2),
            current_production_metrics=prod_metrics_dict,
            improvement_vs_production_pct=imp_vs_prod_pct,
            rejection_reasons=rejection_reasons,
        )

        if is_approved:
            prod_info = (
                f" | +{imp_vs_prod_pct:.1f}% vs Prod" if imp_vs_prod_pct is not None else ""
            )
            logger.info(
                f"✅ Model APPROVED by Acceptance Gate! (MAE={candidate_metrics.mae:.2f}, "
                f"Improvement={mae_imp_pct:.1f}% vs {strongest_baseline_name}{prod_info})"
            )
        else:
            logger.warning(
                f"❌ Model REJECTED by Acceptance Gate! Reasons: {rejection_reasons}"
            )

        return report
