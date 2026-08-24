from dataclasses import dataclass
import logging
from typing import Dict, Any

import numpy as np
import pandas as pd

logger = logging.getLogger("ml_baselines")


@dataclass
class ForecastMetrics:
    mae: float
    rmse: float
    mape: float

    def to_dict(self) -> Dict[str, float]:
        return {
            "MAE": round(self.mae, 3),
            "RMSE": round(self.rmse, 3),
            "MAPE_pct": round(self.mape, 2),
        }


def calculate_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> ForecastMetrics:
    """Computes Mean Absolute Error, Root Mean Squared Error, and Mean Absolute Percentage Error."""
    y_t = np.array(y_true, dtype=float)
    y_p = np.array(y_pred, dtype=float)

    mae = float(np.mean(np.abs(y_t - y_p)))
    rmse = float(np.sqrt(np.mean((y_t - y_p) ** 2)))
    # Avoid zero division with small epsilon
    mape = float(np.mean(np.abs((y_t - y_p) / np.maximum(y_t, 1e-4))) * 100.0)

    return ForecastMetrics(mae=mae, rmse=rmse, mape=mape)


class NaiveDemandBaseline:
    """
    Baseline 1: Tomorrow's forecasted demand equals yesterday's actual demand (lag_1_demand).
    """

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        if "lag_1_demand" in df.columns:
            return df["lag_1_demand"].to_numpy()
        raise ValueError("Missing 'lag_1_demand' feature column for Naive forecast.")


class MovingAverageDemandBaseline:
    """
    Baseline 2: Tomorrow's forecasted demand equals the 7-day rolling average demand (rolling_mean_7d).
    """

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        if "rolling_mean_7d" in df.columns:
            return df["rolling_mean_7d"].to_numpy()
        raise ValueError("Missing 'rolling_mean_7d' feature column for Moving Average forecast.")


class BaselineEvaluator:
    """
    Evaluates benchmark baseline models on Validation and Test sets.
    """

    def __init__(self, target_column: str = "demand_target"):
        self.target_column = target_column
        self.naive_model = NaiveDemandBaseline()
        self.ma_model = MovingAverageDemandBaseline()

    def evaluate_split(
        self, split_name: str, df: pd.DataFrame
    ) -> Dict[str, Dict[str, float]]:
        if self.target_column not in df.columns:
            raise ValueError(f"Target column '{self.target_column}' missing in dataset.")

        y_true = df[self.target_column].to_numpy()

        # Naive predictions
        y_naive = self.naive_model.predict(df)
        naive_metrics = calculate_metrics(y_true, y_naive)

        # 7-day MA predictions
        y_ma = self.ma_model.predict(df)
        ma_metrics = calculate_metrics(y_true, y_ma)

        results = {
            "Naive_Baseline": naive_metrics.to_dict(),
            "7Day_Moving_Average": ma_metrics.to_dict(),
        }

        logger.info(
            f"Baseline evaluation on {split_name} ({len(df)} rows):\n"
            f"  - Naive: MAE={naive_metrics.mae:.2f}, RMSE={naive_metrics.rmse:.2f}, MAPE={naive_metrics.mape:.1f}%\n"
            f"  - 7-Day MA: MAE={ma_metrics.mae:.2f}, RMSE={ma_metrics.rmse:.2f}, MAPE={ma_metrics.mape:.1f}%"
        )
        return results
