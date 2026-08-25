from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import logging
from typing import List, Optional

from ml_monitoring.app.schemas import (
    DriftAssessmentReport,
    DriftStatus,
    PerformanceEvaluationReport,
)

logger = logging.getLogger("ml_retraining_policy")


class TriggerType(str, Enum):
    PERFORMANCE_DEGRADATION = "PERFORMANCE_DEGRADATION"
    FEATURE_OR_PREDICTION_DRIFT = "FEATURE_OR_PREDICTION_DRIFT"
    SCHEDULED_CADENCE = "SCHEDULED_CADENCE"
    MANUAL_OVERRIDE = "MANUAL_OVERRIDE"
    NONE = "NONE"


class TriggerSeverity(str, Enum):
    CRITICAL = "CRITICAL"
    WARNING = "WARNING"
    NONE = "NONE"


@dataclass
class RetrainingDecision:
    triggered: bool
    trigger_type: TriggerType
    severity: TriggerSeverity
    evaluated_at: str
    reasons: List[str]
    current_metrics: dict


class RetrainingPolicy:
    """
    Evaluates whether automated model retraining should be triggered
    by separating data/prediction drift signals from performance degradation signals.
    """

    def __init__(
        self,
        max_degradation_ratio: float = 1.50,
        psi_critical_threshold: float = 0.25,
        max_model_age_days: int = 30,
    ):
        self.max_degradation_ratio = max_degradation_ratio
        self.psi_critical_threshold = psi_critical_threshold
        self.max_model_age_days = max_model_age_days

    def evaluate(
        self,
        performance_report: Optional[PerformanceEvaluationReport] = None,
        drift_report: Optional[DriftAssessmentReport] = None,
        last_trained_date: Optional[str] = None,
        manual_trigger: bool = False,
    ) -> RetrainingDecision:
        reasons: List[str] = []
        trigger_type = TriggerType.NONE
        severity = TriggerSeverity.NONE
        metrics: dict = {}

        now_iso = datetime.now(timezone.utc).isoformat()

        # 1. Manual Override
        if manual_trigger:
            return RetrainingDecision(
                triggered=True,
                trigger_type=TriggerType.MANUAL_OVERRIDE,
                severity=TriggerSeverity.WARNING,
                evaluated_at=now_iso,
                reasons=["Manual retraining trigger requested by operator."],
                current_metrics={},
            )

        # 2. Performance Degradation (Highest Priority / Critical)
        if performance_report:
            overall = performance_report.overall_performance
            metrics["production_mae"] = overall.mae
            metrics["baseline_mae"] = overall.baseline_mae
            metrics["degradation_ratio"] = overall.degradation_ratio

            if overall.degradation_ratio > self.max_degradation_ratio:
                reasons.append(
                    f"Production MAE ({overall.mae:.2f}) degraded by {overall.degradation_ratio:.2f}x "
                    f"vs baseline ({overall.baseline_mae:.2f}), exceeding threshold ({self.max_degradation_ratio}x)."
                )
                trigger_type = TriggerType.PERFORMANCE_DEGRADATION
                severity = TriggerSeverity.CRITICAL

        # 3. Feature / Prediction Drift (Warning / Secondary Priority)
        if drift_report:
            metrics["max_psi"] = drift_report.max_psi_score
            metrics["drift_status"] = drift_report.overall_status.value

            if drift_report.overall_status == DriftStatus.SIGNIFICANT_DRIFT:
                reasons.append(
                    f"Significant distribution drift detected (Max PSI: {drift_report.max_psi_score:.3f} >= {self.psi_critical_threshold})."
                )
                if trigger_type == TriggerType.NONE:
                    trigger_type = TriggerType.FEATURE_OR_PREDICTION_DRIFT
                    severity = TriggerSeverity.WARNING

        # 4. Scheduled Cadence (Model Age)
        if last_trained_date:
            try:
                last_dt = datetime.fromisoformat(last_trained_date.replace("Z", "+00:00"))
                age_days = (datetime.now(timezone.utc) - last_dt).days
                metrics["model_age_days"] = age_days
                if age_days >= self.max_model_age_days:
                    reasons.append(
                        f"Model age ({age_days} days) exceeded maximum scheduled cadence ({self.max_model_age_days} days)."
                    )
                    if trigger_type == TriggerType.NONE:
                        trigger_type = TriggerType.SCHEDULED_CADENCE
                        severity = TriggerSeverity.WARNING
            except Exception as e:
                logger.warning(f"Could not parse last_trained_date: {e}")

        triggered = len(reasons) > 0
        logger.info(
            f"Retraining Policy Evaluated: Triggered={triggered}, Type={trigger_type.value}, Severity={severity.value}"
        )

        return RetrainingDecision(
            triggered=triggered,
            trigger_type=trigger_type,
            severity=severity,
            evaluated_at=now_iso,
            reasons=reasons,
            current_metrics=metrics,
        )
