from datetime import datetime, timezone
import logging
from typing import Optional

from ml_monitoring.app.drift_detector import DriftDetector
from ml_monitoring.app.metrics_tracker import InferenceMetricsTracker
from ml_monitoring.app.prediction_logger import PredictionLogger
from ml_monitoring.app.schemas import (
    DriftAssessmentReport,
    DriftStatus,
    MonitoringSummaryReport,
    PerformanceEvaluationReport,
)

logger = logging.getLogger("monitoring_reporter")


class MonitoringReporter:
    """
    Compiles operational inference metrics, distribution drift status,
    and actuals-vs-predicted performance into a holistic monitoring report.
    """

    def __init__(
        self,
        metrics_tracker: InferenceMetricsTracker,
        prediction_logger: PredictionLogger,
        drift_detector: DriftDetector,
    ):
        self.metrics_tracker = metrics_tracker
        self.prediction_logger = prediction_logger
        self.drift_detector = drift_detector

    def compile_summary_report(
        self,
        latest_drift_report: Optional[DriftAssessmentReport] = None,
        latest_perf_report: Optional[PerformanceEvaluationReport] = None,
    ) -> MonitoringSummaryReport:
        op_metrics = self.metrics_tracker.get_metrics()
        action_items = []
        status = "HEALTHY"

        drift_dict = None
        if latest_drift_report:
            drift_dict = {
                "overall_status": latest_drift_report.overall_status.value,
                "max_psi_score": latest_drift_report.max_psi_score,
                "retraining_recommended": latest_drift_report.retraining_recommended,
            }
            if latest_drift_report.overall_status == DriftStatus.SIGNIFICANT_DRIFT:
                status = "CRITICAL"
                action_items.append("Significant feature/prediction drift detected (PSI >= 0.25). Trigger model retraining.")
            elif latest_drift_report.overall_status == DriftStatus.MODERATE_DRIFT:
                if status != "CRITICAL":
                    status = "WARNING"
                action_items.append("Moderate drift detected. Monitor upcoming distribution shifts.")

        perf_dict = None
        if latest_perf_report:
            overall = latest_perf_report.overall_performance
            perf_dict = {
                "overall_mae": overall.mae,
                "overall_rmse": overall.rmse,
                "overall_mape_pct": overall.mape_pct,
                "degradation_ratio": overall.degradation_ratio,
                "status": overall.status,
                "retraining_recommended": overall.retraining_recommended,
            }
            if overall.status == "DEGRADED":
                status = "CRITICAL"
                action_items.append(f"Model accuracy degraded (MAE {overall.mae:.2f} > {overall.baseline_mae:.2f} baseline). Retraining required.")

        if op_metrics.get("error_rate_pct", 0.0) > 5.0:
            status = "CRITICAL"
            action_items.append(f"High inference error rate ({op_metrics['error_rate_pct']}%). Check service health.")
        elif op_metrics.get("p95_latency_ms", 0.0) > 200.0:
            if status == "HEALTHY":
                status = "WARNING"
            action_items.append(f"Elevated p95 latency ({op_metrics['p95_latency_ms']}ms).")

        if not action_items:
            action_items.append("All monitoring signals healthy. System operating within nominal parameters.")

        return MonitoringSummaryReport(
            timestamp=datetime.now(timezone.utc).isoformat(),
            system_status=status,
            operational_metrics=op_metrics,
            drift_summary=drift_dict,
            performance_summary=perf_dict,
            action_items=action_items,
        )
