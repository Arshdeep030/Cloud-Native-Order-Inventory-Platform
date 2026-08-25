from collections import deque
from datetime import datetime, timezone
import logging
from typing import Any, Dict

import numpy as np

logger = logging.getLogger("metrics_tracker")


class InferenceMetricsTracker:
    """
    Tracks real-time operational inference metrics: request count, error count,
    latency percentiles (p50, p95, p99), and forecast count.
    """

    def __init__(self, max_latency_samples: int = 1000):
        self.request_count: int = 0
        self.error_count: int = 0
        self.forecast_count: int = 0
        self.latencies: deque = deque(maxlen=max_latency_samples)
        self.last_reset: str = datetime.now(timezone.utc).isoformat()

    def record_request(
        self,
        latency_ms: float,
        is_error: bool = False,
        forecast_items: int = 1,
    ):
        """Records an inference event."""
        self.request_count += 1
        if is_error:
            self.error_count += 1
        self.forecast_count += forecast_items
        self.latencies.append(latency_ms)

    def get_metrics(self) -> Dict[str, Any]:
        """Calculates current summary metrics."""
        lat_list = list(self.latencies)
        p50 = float(np.percentile(lat_list, 50)) if lat_list else 0.0
        p95 = float(np.percentile(lat_list, 95)) if lat_list else 0.0
        p99 = float(np.percentile(lat_list, 99)) if lat_list else 0.0
        avg_lat = float(np.mean(lat_list)) if lat_list else 0.0

        error_rate = (
            (self.error_count / self.request_count * 100.0)
            if self.request_count > 0
            else 0.0
        )

        return {
            "request_count": self.request_count,
            "error_count": self.error_count,
            "forecast_count": self.forecast_count,
            "error_rate_pct": round(error_rate, 2),
            "avg_latency_ms": round(avg_lat, 2),
            "p50_latency_ms": round(p50, 2),
            "p95_latency_ms": round(p95, 2),
            "p99_latency_ms": round(p99, 2),
            "tracked_since": self.last_reset,
        }

    def reset(self):
        """Resets counters."""
        self.request_count = 0
        self.error_count = 0
        self.forecast_count = 0
        self.latencies.clear()
        self.last_reset = datetime.now(timezone.utc).isoformat()
