from app.logging_config import configure_logging
from app.messaging.order_consumer import start_order_event_consumer


if __name__ == "__main__":
    configure_logging("order-worker")
    start_order_event_consumer()
