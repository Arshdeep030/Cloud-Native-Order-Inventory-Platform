import pytest

from ml_monitoring.app.metrics_tracker import InferenceMetricsTracker


def test_metrics_tracker_calculations():
    tracker = InferenceMetricsTracker()

    tracker.record_request(latency_ms=10.0, is_error=False, forecast_items=7)
    tracker.record_request(latency_ms=20.0, is_error=False, forecast_items=7)
    tracker.record_request(latency_ms=30.0, is_error=True, forecast_items=7)

    metrics = tracker.get_metrics()

    assert metrics["request_count"] == 3
    assert metrics["error_count"] == 1
    assert metrics["forecast_count"] == 21
    assert metrics["error_rate_pct"] == 33.33
    assert metrics["avg_latency_ms"] == 20.0
    assert metrics["p50_latency_ms"] == 20.0
