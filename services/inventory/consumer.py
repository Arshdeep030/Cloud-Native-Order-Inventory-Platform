import json
import os
import time
import uuid

import pika
from sqlalchemy.orm import Session

try:
    from database import SessionLocal
    from repository import (
        get_inventory,
        create_reservation,
        release_inventory,
        event_already_processed,
        mark_event_processed,
    )
    from publisher import publish_inventory_event
    from events import Event
except ImportError:
    from services.inventory.database import SessionLocal
    from services.inventory.repository import (
        get_inventory,
        create_reservation,
        release_inventory,
        event_already_processed,
        mark_event_processed,
    )
    from services.inventory.publisher import publish_inventory_event
    from services.inventory.events import Event


RABBITMQ_HOST = os.getenv(
    "RABBITMQ_HOST",
    "localhost"
)


def handle_order_created(event: dict, db: Session) -> bool:
    event_id = event.get("event_id")
    event_type = event.get("event_type")
    correlation_id = event.get("correlation_id", str(uuid.uuid4()))
    payload = event.get("payload", {})
    order_id = payload.get("order_id")
    amount = payload.get("total_amount", payload.get("amount", 0.0))
    items = payload.get("items", [])

    print(
        f"event_type={event_type} "
        f"event_id={event_id} "
        f"correlation_id={correlation_id} "
        f"order_id={order_id}",
        flush=True
    )

    if event_id and event_already_processed(db, event_id):
        print(f"Event {event_id} already processed by Inventory Service, skipping", flush=True)
        return True

    for item in items:
        inventory = get_inventory(
            db,
            item["product_id"]
        )

        if not inventory:
            db.rollback()
            if event_id:
                mark_event_processed(db, event_id)
                db.commit()

            rejected_event = Event(
                event_type="InventoryRejected",
                correlation_id=correlation_id,
                payload={
                    "order_id": order_id,
                    "reason": f"Inventory not found for product {item['product_id']}"
                }
            )
            publish_inventory_event(
                "inventory.rejected",
                rejected_event.to_dict()
            )
            return False

        available_quantity = (
            inventory.quantity
            - inventory.reserved_quantity
        )

        if available_quantity < item["quantity"]:
            db.rollback()
            if event_id:
                mark_event_processed(db, event_id)
                db.commit()

            rejected_event = Event(
                event_type="InventoryRejected",
                correlation_id=correlation_id,
                payload={
                    "order_id": order_id,
                    "reason": f"Insufficient inventory for product {item['product_id']}"
                }
            )
            publish_inventory_event(
                "inventory.rejected",
                rejected_event.to_dict()
            )
            return False

    # Reserve inventory and create audit records only after ALL items have been validated
    for item in items:
        inventory = get_inventory(
            db,
            item["product_id"]
        )
        inventory.reserved_quantity += item["quantity"]
        create_reservation(
            db,
            order_id=order_id,
            product_id=item["product_id"],
            quantity=item["quantity"]
        )

    if event_id:
        mark_event_processed(db, event_id)

    db.commit()

    reserved_event = Event(
        event_type="InventoryReserved",
        correlation_id=correlation_id,
        payload={
            "order_id": order_id,
            "amount": amount,
            "items": items
        }
    )
    publish_inventory_event(
        "inventory.reserved",
        reserved_event.to_dict()
    )
    return True


def handle_payment_failed(event: dict, db: Session) -> bool:
    event_id = event.get("event_id")
    event_type = event.get("event_type")
    correlation_id = event.get("correlation_id", str(uuid.uuid4()))
    payload = event.get("payload", {})
    order_id = payload.get("order_id")

    print(
        f"event_type={event_type} "
        f"event_id={event_id} "
        f"correlation_id={correlation_id} "
        f"order_id={order_id} (Releasing Inventory - Compensation)",
        flush=True
    )

    if event_id and event_already_processed(db, event_id):
        print(f"Event {event_id} already processed by Inventory Service, skipping", flush=True)
        return True

    if order_id:
        release_inventory(db, order_id)

    if event_id:
        mark_event_processed(db, event_id)

    db.commit()

    released_event = Event(
        event_type="InventoryReleased",
        correlation_id=correlation_id,
        payload={
            "order_id": order_id
        }
    )
    publish_inventory_event(
        "inventory.released",
        released_event.to_dict()
    )
    return True


def callback(
    channel,
    method,
    properties,
    body
):
    try:
        event = json.loads(body)
    except Exception as e:
        print(f"Failed to decode JSON message in Inventory Service: {e}", flush=True)
        channel.basic_ack(delivery_tag=method.delivery_tag)
        return

    db: Session = SessionLocal()

    try:
        if method.routing_key == "payment.failed" or event.get("event_type") == "PaymentFailed":
            handle_payment_failed(event, db)
        else:
            handle_order_created(event, db)

        channel.basic_ack(
            delivery_tag=method.delivery_tag
        )
    except Exception as e:
        db.rollback()
        print(
            f"Error processing inventory event: {e}",
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
                f"RabbitMQ not ready yet, retrying in {retry_interval}s... ({i + 1}/{max_retries})",
                flush=True
            )
            time.sleep(retry_interval)

    if connection is None:
        raise RuntimeError("Could not connect to RabbitMQ")

    channel = connection.channel()

    # Topology: Exchanges
    channel.exchange_declare(
        exchange="order-events",
        exchange_type="topic",
        durable=True
    )
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

    # Queues & Bindings
    # 1. Order Created -> Inventory
    channel.queue_declare(
        queue="order-created",
        durable=True
    )
    channel.queue_bind(
        exchange="order-events",
        queue="order-created",
        routing_key="order.created"
    )

    # 2. Payment Failed -> Inventory (Compensating transaction)
    channel.queue_declare(
        queue="inventory-payment-failed-queue",
        durable=True
    )
    channel.queue_bind(
        exchange="payment-events",
        queue="inventory-payment-failed-queue",
        routing_key="payment.failed"
    )

    channel.basic_consume(
        queue="order-created",
        on_message_callback=callback
    )
    channel.basic_consume(
        queue="inventory-payment-failed-queue",
        on_message_callback=callback
    )

    print(
        "Inventory Service waiting for events...",
        flush=True
    )

    channel.start_consuming()
