import json
import logging
import os
import time

import pika
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.repositories.order_repository import order_repository
from app.repositories.processed_event_repository import (
    event_already_processed,
    mark_event_processed,
)


from app.config import settings

logger = logging.getLogger(__name__)

RABBITMQ_HOST = settings.rabbitmq_host
RABBITMQ_PORT = settings.rabbitmq_port


def process_order_workflow_event(event: dict, db: Session) -> bool:
    event_id = event.get("event_id")
    event_type = event.get("event_type")
    correlation_id = event.get("correlation_id")
    payload = event.get("payload", {})
    order_id = payload.get("order_id") if isinstance(payload, dict) else event.get("order_id")

    print(
        f"event_type={event_type} "
        f"event_id={event_id} "
        f"correlation_id={correlation_id} "
        f"order_id={order_id}",
        flush=True
    )

    if event_id and event_already_processed(db, event_id):
        print(f"Event {event_id} already processed by Order Worker, skipping", flush=True)
        logger.info("Event %s already processed by Order Worker", event_id)
        return True

    if not order_id:
        logger.warning("Received event without order_id: %s", event)
        if event_id:
            mark_event_processed(db, event_id)
            db.commit()
        return False

    if event_type == "InventoryReserved":
        updated = order_repository.update_order_status(
            db,
            order_id,
            "PAYMENT_PENDING"
        )
        if updated:
            print(f"Order {order_id} inventory reserved -> PAYMENT_PENDING (correlation_id={correlation_id})", flush=True)
            logger.info("Order %s status updated to PAYMENT_PENDING correlation_id=%s", order_id, correlation_id)
        else:
            logger.warning("Order %s not found for InventoryReserved event", order_id)

    elif event_type == "InventoryRejected":
        updated = order_repository.update_order_status(
            db,
            order_id,
            "CANCELLED"
        )
        if updated:
            print(f"Order {order_id} inventory rejected -> CANCELLED (correlation_id={correlation_id})", flush=True)
            logger.info("Order %s status updated to CANCELLED correlation_id=%s", order_id, correlation_id)
        else:
            logger.warning("Order %s not found for InventoryRejected event", order_id)

    elif event_type == "PaymentCompleted":
        updated = order_repository.update_order_status(
            db,
            order_id,
            "CONFIRMED"
        )
        if updated:
            print(f"Order {order_id} payment completed -> CONFIRMED (correlation_id={correlation_id})", flush=True)
            logger.info("Order %s status updated to CONFIRMED correlation_id=%s", order_id, correlation_id)
        else:
            logger.warning("Order %s not found for PaymentCompleted event", order_id)

    elif event_type == "PaymentFailed":
        updated = order_repository.update_order_status(
            db,
            order_id,
            "CANCELLED"
        )
        if updated:
            print(f"Order {order_id} payment failed -> CANCELLED (correlation_id={correlation_id})", flush=True)
            logger.info("Order %s status updated to CANCELLED correlation_id=%s", order_id, correlation_id)
        else:
            logger.warning("Order %s not found for PaymentFailed event", order_id)

    elif event_type == "InventoryReleased":
        print(f"Order {order_id} inventory released (correlation_id={correlation_id})", flush=True)
        logger.info("Order %s inventory released correlation_id=%s", order_id, correlation_id)

    else:
        logger.warning("Unknown event type received: %s", event_type)

    if event_id:
        mark_event_processed(db, event_id)

    db.commit()
    return True


# Backwards compatibility alias
process_inventory_result = process_order_workflow_event


def callback(
    channel,
    method,
    properties,
    body
):
    try:
        event = json.loads(body)
    except Exception as e:
        logger.error("Failed to decode JSON message body: %s", e)
        channel.basic_ack(delivery_tag=method.delivery_tag)
        return

    db: Session = SessionLocal()

    try:
        process_order_workflow_event(event, db)
        channel.basic_ack(
            delivery_tag=method.delivery_tag
        )
    except Exception as e:
        db.rollback()
        logger.error("Error processing order workflow event: %s", e)
        raise
    finally:
        db.close()


def start_order_event_consumer():
    max_retries = 10
    retry_interval = 3
    connection = None

    for i in range(max_retries):
        try:
            connection = pika.BlockingConnection(
                pika.ConnectionParameters(
                    host=RABBITMQ_HOST,
                    port=RABBITMQ_PORT
                )
            )
            break
        except Exception:
            print(
                f"RabbitMQ not ready yet for Order Worker, retrying in {retry_interval}s... ({i + 1}/{max_retries})",
                flush=True
            )
            time.sleep(retry_interval)

    if connection is None:
        raise RuntimeError("Could not connect to RabbitMQ from Order Worker")

    channel = connection.channel()

    # Topic exchanges
    channel.exchange_declare(
        exchange="inventory-events",
        exchange_type="topic",
        durable=True
    )
    channel.exchange_declare(
        exchange="payment-events",
        exchange_type="topic",
        durable=True
    )

    # Queue: order worker consumes both inventory and payment results
    channel.queue_declare(
        queue="inventory-results",
        durable=True
    )

    channel.queue_bind(
        exchange="inventory-events",
        queue="inventory-results",
        routing_key="inventory.*"
    )
    channel.queue_bind(
        exchange="payment-events",
        queue="inventory-results",
        routing_key="payment.*"
    )

    channel.basic_consume(
        queue="inventory-results",
        on_message_callback=callback
    )

    print(
        "Order Service waiting for workflow events (inventory.*, payment.*)...",
        flush=True
    )

    channel.start_consuming()
