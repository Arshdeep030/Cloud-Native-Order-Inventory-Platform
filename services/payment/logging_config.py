import json
import logging
from datetime import datetime, timezone


class JSONFormatter(logging.Formatter):
    def __init__(self, service_name: str = "payment-service"):
        super().__init__()
        self.service_name = service_name

    def format(self, record: logging.LogRecord) -> str:
        log_obj = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "service": getattr(record, "service", self.service_name),
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "correlation_id"):
            log_obj["correlation_id"] = record.correlation_id
        if hasattr(record, "event"):
            log_obj["event"] = record.event
        if hasattr(record, "order_id"):
            log_obj["order_id"] = record.order_id
        if hasattr(record, "event_id"):
            log_obj["event_id"] = record.event_id

        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_obj)


def configure_logging(service_name: str = "payment-service"):
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    while root_logger.handlers:
        root_logger.handlers.pop()
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter(service_name=service_name))
    root_logger.addHandler(handler)
