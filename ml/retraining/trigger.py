import logging
from typing import Any, Dict, Optional

from ml.retraining.policy import RetrainingDecision
from ml.train import run_training_pipeline

logger = logging.getLogger("ml_retraining_trigger")


class RetrainingPipelineRunner:
    """
    Orchestrates the automated execution of the ML training pipeline
    when retraining policy decisions indicate that model refresh is required.
    """

    def __init__(self, tracking_uri: str = "sqlite:///mlflow.db"):
        self.tracking_uri = tracking_uri

    def run_if_triggered(
        self,
        decision: RetrainingDecision,
        dataset_version: str = "demand_features_retrained_v1",
        n_optuna_trials: int = 25,
    ) -> Dict[str, Any]:
        """
        Executes retraining pipeline if the policy decision is triggered.
        """
        if not decision.triggered:
            logger.info(
                "Retraining check evaluated: No triggers active. Pipeline run skipped."
            )
            return {
                "status": "SKIPPED",
                "triggered": False,
                "reasons": decision.reasons,
                "evaluated_at": decision.evaluated_at,
            }

        logger.info(
            f"🚀 Retraining Trigger Activated! Trigger Type: {decision.trigger_type.value}, "
            f"Severity: {decision.severity.value}. Reasons: {decision.reasons}"
        )

        try:
            pipeline_res = run_training_pipeline(
                dataset_version=dataset_version,
                n_optuna_trials=n_optuna_trials,
                tracking_uri=self.tracking_uri,
            )

            return {
                "status": "COMPLETED",
                "triggered": True,
                "trigger_type": decision.trigger_type.value,
                "reasons": decision.reasons,
                "pipeline_result": pipeline_res,
            }
        except Exception as err:
            logger.error(f"Retraining execution failed: {err}", exc_info=True)
            return {
                "status": "FAILED",
                "triggered": True,
                "trigger_type": decision.trigger_type.value,
                "error": str(err),
            }
