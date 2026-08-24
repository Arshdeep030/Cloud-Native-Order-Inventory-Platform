from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel, Field


class ForecastRequest(BaseModel):
    product_id: int = Field(..., ge=1, description="Unique product ID")
    forecast_horizon: int = Field(
        default=7, ge=1, le=30, description="Number of days to forecast (1-30)"
    )
    recent_demand_history: Optional[List[float]] = Field(
        default=None,
        description="List of recent daily demand values (at least 14 days recommended for full lags). If None, defaults to historical base.",
    )
    unit_price: Optional[float] = Field(
        default=49.99, ge=0.0, description="Product selling price"
    )
    start_date: Optional[str] = Field(
        default=None,
        description="Starting date for forecast in YYYY-MM-DD format (defaults to tomorrow)",
    )


class DailyDemandForecast(BaseModel):
    date: str
    day_of_week: int
    predicted_demand: float


class ForecastResponse(BaseModel):
    product_id: int
    model_name: str
    model_version: str
    feature_version: str
    forecast_horizon: int
    total_predicted_demand: float
    daily_forecasts: List[DailyDemandForecast]


class ModelInfoResponse(BaseModel):
    model_name: str
    model_version: str
    feature_version: str
    feature_columns: List[str]
    target_column: str
    is_loaded: bool
    model_uri: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    service: str = "ml-inference-service"
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
