import json
import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

import mlflow
import pandas as pd

from ml.datasets.training_dataset import DatasetMetadata
from ml.evaluation.model_gate import ModelApprovalReport
from ml.models.xgboost_model import DemandForecastingXGBoost
from ml.tuning.optuna_tuner import TuningResult
from ml.validation.time_split import SplitSummary

logger = logging.getLogger("ml_tracking")


def get_git_commit_sha() -> str:
    """Retrieves current Git commit SHA safely."""
    try:
        commit = (
            subprocess.check_output(
                ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL
            )
            .decode("utf-8")
            .strip()
        )
        return commit
    except Exception:
        return "unversioned"


class MLflowExperimentTracker:
    """
    Manages MLflow experiment tracking, parameter/metric logging,
    artifact versioning, and Model Registry promotion for demand forecasting models.
    """

    def __init__(
        self,
        experiment_name: str = "demand_forecasting_platform",
        tracking_uri: Optional[str] = None,
    ):
        self.experiment_name = experiment_name
        self.tracking_uri = tracking_uri or os.getenv(
            "MLFLOW_TRACKING_URI", "sqlite:///mlflow.db"
        )
        mlflow.set_tracking_uri(self.tracking_uri)
        mlflow.set_experiment(self.experiment_name)


    def log_training_run(
        self,
        candidate_model: DemandForecastingXGBoost,
        dataset_metadata: DatasetMetadata,
        split_summary: SplitSummary,
        tuning_result: TuningResult,
        approval_report: ModelApprovalReport,
        registered_model_name: str = "demand_forecasting_xgboost",
    ) -> Dict[str, Any]:
        """
        Logs complete training run parameters, metrics, artifacts, and tags to MLflow.
        """
        git_commit = get_git_commit_sha()

        with mlflow.start_run(run_name=f"xgboost_v1_{dataset_metadata.dataset_version}") as run:
            run_id = run.info.run_id

            # 1. Log Parameters
            mlflow.log_params({
                "dataset_version": dataset_metadata.dataset_version,
                "feature_version": dataset_metadata.feature_version,
                "git_commit": git_commit,
                "train_records": split_summary.train_records,
                "val_records": split_summary.val_records,
                "test_records": split_summary.test_records,
                "train_start": split_summary.train_start,
                "train_end": split_summary.train_end,
                "val_start": split_summary.val_start,
                "val_end": split_summary.val_end,
                "test_start": split_summary.test_start,
                "test_end": split_summary.test_end,
                "optuna_trials": tuning_result.n_trials,
            })
            mlflow.log_params(tuning_result.best_params)

            # 2. Log Metrics
            mlflow.log_metrics({
                "val_mae": tuning_result.best_val_mae,
                "test_mae": approval_report.candidate_metrics["MAE"],
                "test_rmse": approval_report.candidate_metrics["RMSE"],
                "test_mape": approval_report.candidate_metrics["MAPE_pct"],
                "baseline_mae": approval_report.baseline_metrics[approval_report.strongest_baseline]["MAE"],
                "baseline_rmse": approval_report.baseline_metrics[approval_report.strongest_baseline]["RMSE"],
                "mae_improvement_pct": approval_report.mae_improvement_pct,
                "rmse_improvement_pct": approval_report.rmse_improvement_pct,
            })

            # 3. Log Tags
            mlflow.set_tags({
                "model_type": "xgboost",
                "framework": "xgboost-3.4",
                "approval_status": "APPROVED" if approval_report.is_approved else "REJECTED",
                "strongest_baseline": approval_report.strongest_baseline,
            })

            # 4. Log Artifacts
            with tempfile.TemporaryDirectory() as tmp_dir:
                tmp_path = Path(tmp_dir)

                # Save Feature Importances
                feat_imp = candidate_model.get_feature_importances()
                feat_file = tmp_path / "feature_importances.json"
                with open(feat_file, "w") as f:
                    json.dump(feat_imp, f, indent=2)
                mlflow.log_artifact(str(feat_file), artifact_path="metadata")

                # Save Dataset Metadata
                meta_file = tmp_path / "dataset_metadata.json"
                with open(meta_file, "w") as f:
                    f.write(dataset_metadata.model_dump_json(indent=2))
                mlflow.log_artifact(str(meta_file), artifact_path="metadata")

                # Save Acceptance Report
                report_file = tmp_path / "approval_report.json"
                with open(report_file, "w") as f:
                    json.dump(
                        {
                            "is_approved": approval_report.is_approved,
                            "evaluated_at": approval_report.evaluated_at,
                            "test_samples": approval_report.test_samples,
                            "candidate_metrics": approval_report.candidate_metrics,
                            "baseline_metrics": approval_report.baseline_metrics,
                            "mae_improvement_pct": approval_report.mae_improvement_pct,
                            "rejection_reasons": approval_report.rejection_reasons,
                        },
                        f,
                        indent=2,
                    )
                mlflow.log_artifact(str(report_file), artifact_path="metadata")

            # 5. Log Model and Register in MLflow Model Registry (if Approved)
            if approval_report.is_approved:
                mlflow.xgboost.log_model(
                    xgb_model=candidate_model.model,
                    artifact_path="model",
                    registered_model_name=registered_model_name,
                )
                logger.info(
                    f"Registered approved model '{registered_model_name}' into MLflow Model Registry."
                )
            else:
                mlflow.xgboost.log_model(
                    xgb_model=candidate_model.model,
                    artifact_path="model",
                )

            model_uri = f"runs:/{run_id}/model"


            logger.info(
                f"MLflow Run completed ({run_id}). Status: {'APPROVED' if approval_report.is_approved else 'REJECTED'}"
            )

            return {
                "run_id": run_id,
                "model_uri": model_uri,
                "is_approved": approval_report.is_approved,
                "mae_improvement_pct": approval_report.mae_improvement_pct,
            }
