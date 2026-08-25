import logging
import time
from typing import Optional

from fastapi import FastAPI, HTTPException, Request, Response, status

from ml_monitoring.app.config import settings
from ml_monitoring.app.drift_detector import DriftDetector
from ml_monitoring.app.metrics_tracker import InferenceMetricsTracker
from ml_monitoring.app.performance_evaluator import PerformanceEvaluator
from ml_monitoring.app.prediction_logger import PredictionLogger
from ml_monitoring.app.reporter import MonitoringReporter
from ml_monitoring.app.schemas import (
    BatchPredictionLogRequest,
    DriftAssessmentReport,
    MonitoringSummaryReport,
    PerformanceEvaluationReport,
    PerformanceEvaluationRequest,
    PredictionLogRecord,
)

logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "service": "ml-monitoring-service", "logger": "%(name)s", "message": "%(message)s"}',
)
logger = logging.getLogger("ml_monitoring_api")

app = FastAPI(
    title="Cloud-Native ML Monitoring & Observability Service",
    description="Production MLOps monitoring for prediction logging, PSI feature/prediction drift, latency metrics, and performance degradation tracking.",
    version="1.0.0",
)

prediction_logger = PredictionLogger()
metrics_tracker = InferenceMetricsTracker()
drift_detector = DriftDetector()
performance_evaluator = PerformanceEvaluator()
reporter = MonitoringReporter(metrics_tracker, prediction_logger, drift_detector)

latest_drift_report: Optional[DriftAssessmentReport] = None
latest_perf_report: Optional[PerformanceEvaluationReport] = None


@app.middleware("http")
async def track_latency_middleware(request: Request, call_next):
    start_time = time.perf_counter()
    try:
        response = await call_next(request)
        latency_ms = (time.perf_counter() - start_time) * 1000.0
        is_error = response.status_code >= 500
        metrics_tracker.record_request(latency_ms=latency_ms, is_error=is_error)
        return response
    except Exception as exc:
        latency_ms = (time.perf_counter() - start_time) * 1000.0
        metrics_tracker.record_request(latency_ms=latency_ms, is_error=True)
        raise exc


@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "service": "ml-monitoring-service",
        "logs_path": settings.prediction_logs_path,
        "psi_critical_threshold": settings.psi_critical_threshold,
    }


@app.post(
    "/monitoring/log-prediction",
    status_code=status.HTTP_201_CREATED,
    tags=["Prediction Logging"],
)
async def log_prediction(record: PredictionLogRecord):
    """Logs a single model inference prediction to Gold lakehouse storage."""
    try:
        pred_id = prediction_logger.log_prediction(record)
        metrics_tracker.forecast_count += 1
        return {"status": "LOGGED", "prediction_id": pred_id}
    except Exception as err:
        logger.error(f"Failed to log prediction: {err}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Prediction logging failure: {str(err)}",
        )


@app.post(
    "/monitoring/log-predictions/batch",
    status_code=status.HTTP_201_CREATED,
    tags=["Prediction Logging"],
)
async def log_predictions_batch(request: BatchPredictionLogRequest):
    """Logs a batch of prediction records."""
    try:
        ids = prediction_logger.log_batch(request.records)
        metrics_tracker.forecast_count += len(request.records)
        return {"status": "LOGGED", "count": len(ids), "prediction_ids": ids}
    except Exception as err:
        logger.error(f"Failed to log batch predictions: {err}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Batch logging failure: {str(err)}",
        )


@app.post(
    "/monitoring/evaluate-performance",
    response_model=PerformanceEvaluationReport,
    status_code=status.HTTP_200_OK,
    tags=["Performance Evaluation"],
)
async def evaluate_performance(request: PerformanceEvaluationRequest):
    """
    Evaluates actual sales vs logged predictions, calculating MAE, RMSE,
    and MAPE degradation vs baseline acceptance thresholds.
    """
    global latest_perf_report
    try:
        import pandas as pd

        preds_df = prediction_logger.get_recent_predictions()
        if preds_df.empty:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No historical prediction logs found to evaluate.",
            )

        actuals_data = [a.model_dump() for a in request.actuals]
        actuals_df = pd.DataFrame(actuals_data)

        report = performance_evaluator.evaluate(preds_df, actuals_df)
        latest_perf_report = report
        return report
    except HTTPException:
        raise
    except Exception as err:
        logger.error(f"Performance evaluation failed: {err}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Performance evaluation failure: {str(err)}",
        )


@app.get(
    "/monitoring/metrics",
    tags=["Operational Observability"],
)
async def get_operational_metrics():
    """Returns real-time inference latency and error metrics."""
    return metrics_tracker.get_metrics()


@app.get(
    "/monitoring/report",
    response_model=MonitoringSummaryReport,
    tags=["Holistic Reporting"],
)
async def get_monitoring_summary_report():
    """Returns complete system health, drift, and performance summary."""
    return reporter.compile_summary_report(
        latest_drift_report=latest_drift_report,
        latest_perf_report=latest_perf_report,
    )
