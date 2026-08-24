import json
import logging
import sys
import time
import uuid
from datetime import datetime, timezone

import pika

from data_ingestion.config import settings
from data_ingestion.schemas.base import IngestedBronzeEvent
from data_ingestion.writers.bronze_writer import BronzeDataLakeWriter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("data-ingestion")


class DataLakeIngestionConsumer:

    def __init__(self, writer: BronzeDataLakeWriter = None):
        self.writer = writer or BronzeDataLakeWriter(settings.bronze_storage_path)

    def process_message(
        self,
        body: bytes,
        exchange: str = "unknown",
        routing_key: str = "unknown"
    ) -> IngestedBronzeEvent:
        raw_dict = json.loads(body.decode("utf-8") if isinstance(body, bytes) else body)

        event_id = str(raw_dict.get("event_id") or uuid.uuid4())
        event_type = str(raw_dict.get("event_type") or "UnknownEvent")
        occurred_at = str(
            raw_dict.get("occurred_at")
            or raw_dict.get("event_timestamp")
            or datetime.now(timezone.utc).isoformat()
        )
        correlation_id = str(raw_dict.get("correlation_id") or uuid.uuid4())
        payload = raw_dict.get("payload", {})

        bronze_event = IngestedBronzeEvent(
            source_exchange=exchange,
            source_routing_key=routing_key,
            event_id=event_id,
            event_type=event_type,
            occurred_at=occurred_at,
            correlation_id=correlation_id,
            payload=payload
        )

        saved_path = self.writer.write_event(bronze_event)
        logger.info(
            f"Ingested {event_type} ({event_id}) from {exchange}:{routing_key} -> {saved_path}"
        )
        return bronze_event

    def start(self, max_retries: int = 10, retry_interval: int = 3):
        connection = None
        for i in range(max_retries):
            try:
                connection = pika.BlockingConnection(
                    pika.ConnectionParameters(
                        host=settings.rabbitmq_host,
                        port=settings.rabbitmq_port
                    )
                )
                break
            except Exception as e:
                logger.warning(
                    f"RabbitMQ not ready for Data Ingestion, retrying in {retry_interval}s... ({i + 1}/{max_retries}) error: {e}"
                )
                time.sleep(retry_interval)

        if connection is None:
            logger.error("Could not connect to RabbitMQ for Data Ingestion")
            raise RuntimeError("Could not connect to RabbitMQ for Data Ingestion")

        channel = connection.channel()

        # Declare topic exchanges
        exchanges = ["order-events", "inventory-events", "payment-events"]
        for ex in exchanges:
            channel.exchange_declare(exchange=ex, exchange_type="topic", durable=True)

        # Declare dedicated data lake queue
        queue_name = settings.rabbitmq_queue
        channel.queue_declare(queue=queue_name, durable=True)

        # Bind to all events across all domain exchanges
        for ex in exchanges:
            channel.queue_bind(exchange=ex, queue=queue_name, routing_key="#")

        def callback(ch, method, properties, body):
            try:
                self.process_message(
                    body=body,
                    exchange=method.exchange,
                    routing_key=method.routing_key
                )
                ch.basic_ack(delivery_tag=method.delivery_tag)
            except Exception as exc:
                logger.error(f"Failed to ingest event: {exc}", exc_info=True)
                ch.basic_ack(delivery_tag=method.delivery_tag)

        channel.basic_consume(
            queue=queue_name,
            on_message_callback=callback
        )

        logger.info(
            f"Data Lake Ingestion Consumer running on queue '{queue_name}' bound to {exchanges} with wildcard '#'"
        )
        channel.start_consuming()


if __name__ == "__main__":
    consumer = DataLakeIngestionConsumer()
    consumer.start()
