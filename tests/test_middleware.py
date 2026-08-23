import json
import logging
from app.logging_config import JSONFormatter


def test_request_id_is_returned(client):

    response = client.get("/")

    assert response.status_code == 200
    assert "X-Request-ID" in response.headers
    assert response.headers["X-Request-ID"]


def test_request_id_is_preserved(client):

    response = client.get(
        "/",
        headers={
            "X-Request-ID": "test-request-123"
        }
    )

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "test-request-123"


def test_correlation_id_is_preserved(client):

    response = client.get(
        "/",
        headers={
            "X-Request-ID": "test-req-456",
            "X-Correlation-ID": "test-corr-789"
        }
    )

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "test-req-456"
    assert response.headers["X-Correlation-ID"] == "test-corr-789"


def test_json_formatter_structure():
    formatter = JSONFormatter(service_name="test-service")
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg="Test message",
        args=(),
        exc_info=None
    )
    record.request_id = "req-123"
    record.correlation_id = "corr-456"
    record.event = "test_event"

    formatted = formatter.format(record)
    parsed = json.loads(formatted)

    assert parsed["level"] == "INFO"
    assert parsed["service"] == "test-service"
    assert parsed["message"] == "Test message"
    assert parsed["request_id"] == "req-123"
    assert parsed["correlation_id"] == "corr-456"
    assert parsed["event"] == "test_event"
    assert "timestamp" in parsed
