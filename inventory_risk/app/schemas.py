from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class RiskLevel(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class RiskAssessmentRequest(BaseModel):
    product_id: int = Field(..., ge=1, description="Unique product ID")
    current_inventory: int = Field(..., ge=0, description="Current physical inventory in stock")
    safety_stock: Optional[int] = Field(default=15, ge=0, description="Minimum buffer stock")
    forecast_horizon_days: int = Field(default=7, ge=1, le=30, description="Horizon for demand forecast")
    forecasted_demand: Optional[float] = Field(
        default=None, ge=0.0, description="Direct demand forecast override; if omitted, queries ML service"
    )
    unit_price: Optional[float] = Field(default=49.99, ge=0.0, description="Product price for feature alignment")


class RiskAssessmentResult(BaseModel):
    product_id: int
    current_inventory: int
    forecasted_demand: float
    forecast_horizon_days: int
    inventory_position: float
    coverage_ratio: float
    risk_level: RiskLevel
    recommended_reorder_quantity: int
    model_name: str = "demand_forecasting_xgboost"
    model_version: str = "1"
    feature_version: str = "v1"
    assessed_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class InventoryRiskEvent(BaseModel):
    event_id: str
    event_type: str = "InventoryRiskDetected"
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    product_id: int
    current_inventory: int
    forecasted_demand: float
    forecast_horizon_days: int
    risk_level: RiskLevel
    coverage_ratio: float
    recommended_reorder_quantity: int
    model_name: str = "demand_forecasting_xgboost"
    model_version: str = "1"
    feature_version: str = "v1"


class EvaluateAndPublishResponse(BaseModel):
    assessment: RiskAssessmentResult
    event_published: bool
    event_id: Optional[str] = None
    routing_key: Optional[str] = None
