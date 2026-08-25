from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class DriftStatus(str, Enum):
    NO_DRIFT = "NO_DRIFT"
    MODERATE_DRIFT = "MODERATE_DRIFT"
    SIGNIFICANT_DRIFT = "SIGNIFICANT_DRIFT"


class PredictionLogRecord(BaseModel):
    prediction_id: str
    product_id: int
    prediction_date: str
    forecast_horizon: int
    predicted_demand: float
    model_name: str = "demand_forecasting_xgboost"
    model_version: str = "1"
    feature_version: str = "v1"
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    input_features: Optional[Dict[str, float]] = None


class BatchPredictionLogRequest(BaseModel):
    records: List[PredictionLogRecord]


class FeatureDriftResult(BaseModel):
    feature_name: str
    psi_score: float
    status: DriftStatus
    sample_size_reference: int
    sample_size_production: int


class DriftAssessmentReport(BaseModel):
    evaluated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    overall_status: DriftStatus
    max_psi_score: float
    feature_drifts: List[FeatureDriftResult]
    prediction_drift: FeatureDriftResult
    retraining_recommended: bool


class ActualDemandRecord(BaseModel):
    product_id: int
    date: str
    actual_demand: float


class PerformanceEvaluationRequest(BaseModel):
    actuals: List[ActualDemandRecord]


class ModelPerformanceMetric(BaseModel):
    product_id: Optional[int] = None
    evaluated_samples: int
    mae: float
    rmse: float
    mape_pct: float
    baseline_mae: float
    degradation_ratio: float
    status: str  # HEALTHY / DEGRADED
    retraining_recommended: bool


class PerformanceEvaluationReport(BaseModel):
    evaluated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    overall_performance: ModelPerformanceMetric
    product_level_performance: List[ModelPerformanceMetric]
    retraining_recommended: bool


class MonitoringSummaryReport(BaseModel):
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    system_status: str  # HEALTHY / WARNING / CRITICAL
    operational_metrics: Dict[str, Any]
    drift_summary: Optional[Dict[str, Any]] = None
    performance_summary: Optional[Dict[str, Any]] = None
    action_items: List[str] = Field(default_factory=list)
