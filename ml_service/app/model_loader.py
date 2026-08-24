import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import mlflow.xgboost

from ml.datasets.training_dataset import FEATURE_COLUMNS, TARGET_COLUMN
from ml.models.xgboost_model import DemandForecastingXGBoost

logger = logging.getLogger("ml_model_loader")


class ModelLoader:
    """
    Manages loading the active production demand forecasting model
    from MLflow Model Registry or local artifact storage.
    """

    def __init__(
        self,
        model_name: str = "demand_forecasting_xgboost",
        model_version: str = "1",
        feature_version: str = "v1",
        local_model_path: str = "./models/demand_forecast_model.json",
        tracking_uri: Optional[str] = None,
    ):
        self.model_name = model_name
        self.model_version = model_version
        self.feature_version = feature_version
        self.local_model_path = Path(local_model_path)
        self.tracking_uri = tracking_uri or os.getenv("MLFLOW_TRACKING_URI", "sqlite:///mlflow.db")
        self.loaded_model: Optional[DemandForecastingXGBoost] = None
        self.model_source_uri: Optional[str] = None

    def load(self) -> DemandForecastingXGBoost:
        """Loads and caches the production forecasting model."""
        if self.loaded_model is not None:
            return self.loaded_model

        # 1. Attempt loading from MLflow Model Registry
        try:
            mlflow.set_tracking_uri(self.tracking_uri)
            registry_uri = f"models:/{self.model_name}/{self.model_version}"
            logger.info(f"Attempting to load model from MLflow Registry: {registry_uri}")
            xgb_raw = mlflow.xgboost.load_model(registry_uri)
            model_wrapper = DemandForecastingXGBoost(
                feature_columns=FEATURE_COLUMNS,
                target_column=TARGET_COLUMN,
            )
            model_wrapper.model = xgb_raw
            model_wrapper.is_fitted = True
            self.loaded_model = model_wrapper
            self.model_source_uri = registry_uri
            logger.info(f"✓ Loaded production model from MLflow Registry -> {registry_uri}")
            return self.loaded_model
        except Exception as mlflow_err:
            logger.warning(
                f"Could not load from MLflow Registry ({mlflow_err}). Attempting fallback to local artifact..."
            )

        # 2. Fallback to local JSON model artifact
        if self.local_model_path.exists():
            model_wrapper = DemandForecastingXGBoost(
                feature_columns=FEATURE_COLUMNS,
                target_column=TARGET_COLUMN,
            )
            model_wrapper.load_model(str(self.local_model_path))
            self.loaded_model = model_wrapper
            self.model_source_uri = str(self.local_model_path)
            logger.info(f"✓ Loaded model from local artifact -> {self.local_model_path}")
            return self.loaded_model

        # 3. If model doesn't exist yet, initialize baseline fitted instance for robust startup
        logger.warning(
            "No pre-trained model found on disk. Initializing default baseline model instance."
        )
        import pandas as pd
        import numpy as np

        dummy_data = {col: [10.0, 12.0, 14.0] for col in FEATURE_COLUMNS}
        dummy_data[TARGET_COLUMN] = [11.0, 13.0, 15.0]
        dummy_df = pd.DataFrame(dummy_data)
        model_wrapper = DemandForecastingXGBoost(
            feature_columns=FEATURE_COLUMNS,
            target_column=TARGET_COLUMN,
        )
        model_wrapper.fit(dummy_df)
        self.loaded_model = model_wrapper
        self.model_source_uri = "default_fallback_initialization"
        return self.loaded_model

    def get_info(self) -> Dict[str, Any]:
        return {
            "model_name": self.model_name,
            "model_version": self.model_version,
            "feature_version": self.feature_version,
            "feature_columns": FEATURE_COLUMNS,
            "target_column": TARGET_COLUMN,
            "is_loaded": self.loaded_model is not None,
            "model_uri": self.model_source_uri,
        }
