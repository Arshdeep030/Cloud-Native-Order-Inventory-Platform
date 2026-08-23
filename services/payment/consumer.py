import json
import os
import time
import uuid

import pika
from sqlalchemy.orm import Session

try:
    from database import SessionLocal
    from repository import (
        create_payment,
        event_already_processed,
        mark_event_processed,
    )
    from service import payment_service
    from publisher import publish_payment_event
    from events import Event
except ImportError:
    from services.payment.database import SessionLocal
    from services.payment.repository import (
        create_payment,
        event_already_processed,
        mark_event_processed,
    )
    from services.payment.service import payment_service
    from services.payment.publisher import publish_payment_event
    from services.payment.events import Event


RABBITMQ_HOST = os.getenv(
    "RABBITMQ_HOST",
    "localhost"
)


def handle_inventory_reserved(event: dict, db: Session) -> bool:
    event_id = event.get("event_id")
    event_type = event.get("event_type")
    correlation_id = event.get("correlation_id", str(uuid.uuid4()))
    payload = event.get("payload", {})
    order_id = payload.get("order_id")
    amount = float(payload.get("amount", 0.0))

    print(
        f"event_type={event_type} "
        f"event_id={event_id} "
        f"correlation_id={correlation_id} "
        f"order_id={order_id} "
        f"amount={amount}",
        flush=True
    )

    if event_id and event_already_processed(db, event_id):
        print(f"Event {event_id} already processed by Payment Service, skipping", flush=True)
        return True

    if not order_id:
        if event_id:
            mark_event_processed(db, event_id)
            db.commit()
        return False

    status = payment_service.process_payment(db, order_id, amount)
    payment = create_payment(db, order_id, amount, status=status)

    if event_id:
        mark_event_processed(db, event_id)

    db.commit()

    if status == "COMPLETED":
        payment_completed_event = Event(
            event_type="PaymentCompleted",
            correlation_id=correlation_id,
            payload={
                "order_id": order_id,
                "payment_id": payment.id,
                "amount": amount
            }
        )
        publish_payment_event(
            "payment.completed",
            payment_completed_event.to_dict()
        )
        return True
    else:
        payment_failed_event = Event(
            event_type="PaymentFailed",
            correlation_id=correlation_id,
            payload={
                "order_id": order_id,
                "payment_id": payment.id,
                "amount": amount,
                "reason": "Payment declined"
            }
        )
        publish_payment_event(
            "payment.failed",
            payment_failed_event.to_dict()
        )
        return False


def callback(
    channel,
    method,
    properties,
    body
):
    try:
        event = json.loads(body)
    except Exception as e:
        print(f"Failed to decode JSON message in Payment Service: {e}", flush=True)
        channel.basic_ack(delivery_tag=method.delivery_tag)
        return

    db: Session = SessionLocal()

    try:
        handle_inventory_reserved(event, db)
        channel.basic_ack(
            delivery_tag=method.delivery_tag
        )
    except Exception as e:
        db.rollback()
        print(
            f"Error processing payment event: {e}",
            flush=True
        )
        raise
    finally:
        db.close()


def start_consumer():
    max_retries = 10
    retry_interval = 3
    connection = None

    for i in range(max_retries):
        try:
            connection = pika.BlockingConnection(
                pika.ConnectionParameters(
                    host=RABBITMQ_HOST
                )
            )
            break
        except Exception:
            print(
                f"RabbitMQ not ready yet for Payment Service, retrying in {retry_interval}s... ({i + 1}/{max_retries})",
                flush=True
            )
            time.sleep(retry_interval)

    if connection is None:
        raise RuntimeError("Could not connect to RabbitMQ from Payment Service")

    channel = connection.channel()

    # Topology: Exchanges
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

    # Queue: Payment listens to inventory.reserved
    channel.queue_declare(
        queue="payment-inventory-queue",
        durable=True
    )
    channel.queue_bind(
        exchange="inventory-events",
        queue="payment-inventory-queue",
        routing_key="inventory.reserved"
    )

    channel.basic_consume(
        queue="payment-inventory-queue",
        on_message_callback=callback
    )

    print(
        "Payment Service waiting for events...",
        flush=True
    )

    channel.start_consuming()
