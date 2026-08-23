from database import Base, engine
from consumer import start_consumer
from logging_config import configure_logging

try:
    Base.metadata.create_all(
        bind=engine
    )
except Exception:
    pass


if __name__ == "__main__":
    configure_logging("payment-service")
    start_consumer()
