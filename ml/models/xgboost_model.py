import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import xgboost as xgb

from ml.datasets.training_dataset import FEATURE_COLUMNS, TARGET_COLUMN

logger = logging.getLogger("ml_xgboost")


class DemandForecastingXGBoost:
    """
    XGBoost Regression Model for Product Demand Forecasting.
    """

    def __init__(
        self,
        feature_columns: Optional[List[str]] = None,
        target_column: str = TARGET_COLUMN,
        params: Optional[Dict[str, Any]] = None,
    ):
        self.feature_columns = feature_columns or FEATURE_COLUMNS
        self.target_column = target_column
        self.params = params or {
            "n_estimators": 50,
            "max_depth": 3,
            "learning_rate": 0.05,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "min_child_weight": 2,
            "random_state": 42,
            "objective": "reg:squarederror",
        }
        self.model = xgb.XGBRegressor(**self.params)
        self.is_fitted = False

    def fit(
        self,
        train_df: pd.DataFrame,
        eval_df: Optional[pd.DataFrame] = None,
        verbose: bool = False,
    ) -> "DemandForecastingXGBoost":
        """Trains the XGBoost regressor strictly on the training partition."""
        X_train = train_df[self.feature_columns]
        y_train = train_df[self.target_column]

        eval_set = []
        if eval_df is not None:
            X_eval = eval_df[self.feature_columns]
            y_eval = eval_df[self.target_column]
            eval_set.append((X_eval, y_eval))

        self.model.fit(
            X_train,
            y_train,
            eval_set=eval_set if eval_set else None,
            verbose=verbose,
        )
        self.is_fitted = True
        logger.info(f"Fitted DemandForecastingXGBoost with {len(train_df)} training samples.")
        return self

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        """Generates demand forecasts, clipping negative values to 0."""
        if not self.is_fitted:
            raise RuntimeError("Model must be fitted before generating predictions.")

        X = df[self.feature_columns]
        preds = self.model.predict(X)
        # Demand cannot be negative
        return np.maximum(0.0, preds)

    def get_feature_importances(self) -> Dict[str, float]:
        """Returns sorted feature importances."""
        if not self.is_fitted:
            raise RuntimeError("Model must be fitted to retrieve feature importances.")

        importances = self.model.feature_importances_
        feature_imp_map = {
            col: round(float(imp), 4)
            for col, imp in zip(self.feature_columns, importances)
        }
        return dict(
            sorted(feature_imp_map.items(), key=lambda item: item[1], reverse=True)
        )

    def save_model(self, filepath: str):
        """Saves model weights and configuration to a file."""
        p = Path(filepath)
        p.parent.mkdir(parents=True, exist_ok=True)
        self.model.save_model(str(p))
        logger.info(f"Saved XGBoost model artifact -> {filepath}")

    def load_model(self, filepath: str) -> "DemandForecastingXGBoost":
        """Loads model weights from file."""
        p = Path(filepath)
        if not p.exists():
            raise FileNotFoundError(f"Model file not found: {filepath}")

        self.model = xgb.XGBRegressor()
        self.model.load_model(str(p))
        self.is_fitted = True
        logger.info(f"Loaded XGBoost model artifact from {filepath}")
        return self
