from datetime import datetime, timedelta, timezone
import logging
from typing import List, Optional

import numpy as np
import pandas as pd

from ml.datasets.training_dataset import FEATURE_COLUMNS, TARGET_COLUMN
from ml.models.xgboost_model import DemandForecastingXGBoost
from ml_service.app.schemas import DailyDemandForecast, ForecastRequest, ForecastResponse

logger = logging.getLogger("ml_predictor")


class RecursiveDemandPredictor:
    """
    Executes recursive multi-step autoregressive demand forecasting.
    Dynamically generates lag and rolling window features for future steps
    to preserve feature contracts.
    """

    def __init__(
        self,
        model: DemandForecastingXGBoost,
        model_name: str = "demand_forecasting_xgboost",
        model_version: str = "1",
        feature_version: str = "v1",
    ):
        self.model = model
        self.model_name = model_name
        self.model_version = model_version
        self.feature_version = feature_version

    def forecast(self, request: ForecastRequest) -> ForecastResponse:
        # 1. Determine Start Date
        if request.start_date:
            try:
                base_date = datetime.strptime(request.start_date, "%Y-%m-%d")
            except ValueError:
                base_date = datetime.now(timezone.utc) + timedelta(days=1)
        else:
            base_date = datetime.now(timezone.utc) + timedelta(days=1)

        # 2. Initialize 14-day history buffer for lag extraction
        if request.recent_demand_history and len(request.recent_demand_history) > 0:
            history_buffer = list(request.recent_demand_history)
            if len(history_buffer) < 14:
                # Pad with first element or average
                pad_val = float(np.mean(history_buffer))
                history_buffer = [pad_val] * (14 - len(history_buffer)) + history_buffer
        else:
            # Default realistic base sequence for product
            base_val = 15.0 + (request.product_id * 2.0)
            history_buffer = [base_val + (i % 3) for i in range(14)]

        daily_forecasts: List[DailyDemandForecast] = []

        # 3. Recursive Forecasting Loop
        for step in range(request.forecast_horizon):
            curr_date = base_date + timedelta(days=step)
            dow = curr_date.weekday() + 1  # 1 (Monday) to 7 (Sunday)
            dom = curr_date.day
            month = curr_date.month
            is_weekend = 1 if curr_date.weekday() in [5, 6] else 0

            # Compute dynamic lag features
            lag_1 = float(history_buffer[-1])
            lag_7 = float(history_buffer[-7])
            lag_14 = float(history_buffer[-14])

            # Compute dynamic rolling window features
            rolling_7_mean = float(np.mean(history_buffer[-7:]))
            rolling_7_std = float(np.std(history_buffer[-7:]))
            rolling_14_mean = float(np.mean(history_buffer[-14:]))

            feature_dict = {
                "lag_1_demand": [lag_1],
                "lag_7_demand": [lag_7],
                "lag_14_demand": [lag_14],
                "rolling_mean_7d": [rolling_7_mean],
                "rolling_std_7d": [rolling_7_std],
                "rolling_mean_14d": [rolling_14_mean],
                "day_of_week": [dow],
                "day_of_month": [dom],
                "month": [month],
                "is_weekend": [is_weekend],
                "avg_price": [float(request.unit_price or 49.99)],
            }

            step_df = pd.DataFrame(feature_dict)

            # Model prediction
            pred_arr = self.model.predict(step_df)
            pred_val = max(0.0, float(pred_arr[0]))

            # Append prediction to history buffer for subsequent recursive lags (t+1)
            history_buffer.append(pred_val)

            daily_forecasts.append(
                DailyDemandForecast(
                    date=curr_date.strftime("%Y-%m-%d"),
                    day_of_week=dow,
                    predicted_demand=round(pred_val, 2),
                )
            )

        total_demand = round(sum(d.predicted_demand for d in daily_forecasts), 2)

        return ForecastResponse(
            product_id=request.product_id,
            model_name=self.model_name,
            model_version=self.model_version,
            feature_version=self.feature_version,
            forecast_horizon=request.forecast_horizon,
            total_predicted_demand=total_demand,
            daily_forecasts=daily_forecasts,
        )
