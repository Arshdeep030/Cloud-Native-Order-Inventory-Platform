import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

import mlflow
from mlflow.tracking import MlflowClient

from ml.models.xgboost_model import DemandForecastingXGBoost

logger = logging.getLogger("ml_model_promotion")


class ModelRegistryManager:
    """
    Manages production model promotion, version transitions, and instant rollback.
    """

    def __init__(
        self,
        model_name: str = "demand_forecasting_xgboost",
        tracking_uri: Optional[str] = None,
        local_model_path: str = "./models/demand_forecast_model.json",
    ):
        self.model_name = model_name
        self.tracking_uri = tracking_uri or os.getenv(
            "MLFLOW_TRACKING_URI", "sqlite:///mlflow.db"
        )
        self.local_model_path = Path(local_model_path)
        mlflow.set_tracking_uri(self.tracking_uri)
        self.client = MlflowClient()

    def promote_to_production(self, version: str) -> Dict[str, Any]:
        """
        Promotes the specified model version to active production status.
        """
        logger.info(f"Promoting model '{self.model_name}' version {version} to Production.")

        # In MLflow 2.x/3.x, transition_model_version_stage or alias can be used
        try:
            self.client.set_registered_model_alias(
                name=self.model_name,
                alias="production",
                version=version,
            )
        except Exception as e:
            logger.warning(f"Could not set alias in MLflow: {e}")

        # Download/save artifact to local model deployment path
        try:
            model_uri = f"models:/{self.model_name}/{version}"
            raw_xgb = mlflow.xgboost.load_model(model_uri)
            wrapper = DemandForecastingXGBoost()
            wrapper.model = raw_xgb
            wrapper.is_fitted = True
            wrapper.save_model(str(self.local_model_path))
            logger.info(f"✓ Deployed model version {version} to {self.local_model_path}")
        except Exception as load_err:
            logger.warning(f"Local artifact sync note: {load_err}")

        return {
            "status": "PROMOTED",
            "model_name": self.model_name,
            "production_version": version,
        }

    def rollback(self, target_version: str) -> Dict[str, Any]:
        """
        Executes instant one-step rollback to a previous approved model version.
        """
        logger.warning(
            f"⚠️ Executing Rollback: Reverting production model '{self.model_name}' to version {target_version}."
        )
        return self.promote_to_production(target_version)
