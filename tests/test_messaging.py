import json
from unittest.mock import patch, ANY

import pika

from app.messaging.events import Event, create_correlation_id
from app.messaging.publisher import publish_order_created
from app.messaging.rabbitmq import get_connection
from app.messaging.topology import ORDER_EXCHANGE, INVENTORY_EXCHANGE, PAYMENT_EXCHANGE


def register_and_login(client, email: str):
    client.post(
        "/auth/register",
        json={"email": email, "password": "password123"}
    )
    login = client.post(
        "/auth/login",
        json={"email": email, "password": "password123"}
    )
    return login.json()["access_token"], {
        "Authorization": f"Bearer {login.json()['access_token']}"
    }


def test_event_generates_event_id():
    event = Event(
        event_type="OrderCreated",
        correlation_id="test-corr-id",
        payload={}
    )
    assert event.event_id is not None
    assert len(event.event_id) > 0


def test_event_correlation_id():
    event = Event(
        event_type="OrderCreated",
        correlation_id="abc123",
        payload={}
    )
    assert event.correlation_id == "abc123"


def test_event_to_dict():
    event = Event(
        event_type="OrderCreated",
        correlation_id="abc123",
        payload={
            "order_id": 101
        }
    )
    data = event.to_dict()

    assert data["event_type"] == "OrderCreated"
    assert data["correlation_id"] == "abc123"
    assert data["payload"]["order_id"] == 101
    assert "event_id" in data
    assert "occurred_at" in data


def test_order_exchange_topic_routing():
    conn = get_connection()
    ch = conn.channel()

    ch.exchange_declare(exchange=ORDER_EXCHANGE, exchange_type="topic", durable=True)

    test_queue = "test-order-routing-queue"
    ch.queue_declare(queue=test_queue, durable=True)
    ch.queue_bind(exchange=ORDER_EXCHANGE, queue=test_queue, routing_key="order.created")
    ch.queue_purge(queue=test_queue)

    event = Event(
        event_type="OrderCreated",
        correlation_id="corr-1",
        payload={"order_id": 1}
    )

    # 1. Matching routing key: "order.created"
    ch.basic_publish(
        exchange=ORDER_EXCHANGE,
        routing_key="order.created",
        body=json.dumps(event.to_dict()),
        properties=pika.BasicProperties(delivery_mode=2)
    )

    method, _, body = ch.basic_get(queue=test_queue, auto_ack=True)
    assert method is not None
    received = json.loads(body)
    assert received["payload"]["order_id"] == 1
    assert received["correlation_id"] == "corr-1"

    # 2. Non-matching routing key: "order.cancelled"
    ch.basic_publish(
        exchange=ORDER_EXCHANGE,
        routing_key="order.cancelled",
        body=json.dumps({"event_type": "OrderCancelled", "payload": {"order_id": 2}}),
        properties=pika.BasicProperties(delivery_mode=2)
    )

    method_unmatched, _, _ = ch.basic_get(queue=test_queue, auto_ack=True)
    assert method_unmatched is None

    ch.queue_delete(queue=test_queue)
    conn.close()


def test_inventory_exchange_topic_routing():
    conn = get_connection()
    ch = conn.channel()

    ch.exchange_declare(exchange=INVENTORY_EXCHANGE, exchange_type="topic", durable=True)

    test_queue = "test-inventory-routing-queue"
    ch.queue_declare(queue=test_queue, durable=True)
    ch.queue_bind(exchange=INVENTORY_EXCHANGE, queue=test_queue, routing_key="inventory.*")
    ch.queue_purge(queue=test_queue)

    # 1. Matching routing key: "inventory.reserved"
    event_res = Event(
        event_type="InventoryReserved",
        correlation_id="corr-10",
        payload={"order_id": 10}
    )
    ch.basic_publish(
        exchange=INVENTORY_EXCHANGE,
        routing_key="inventory.reserved",
        body=json.dumps(event_res.to_dict()),
        properties=pika.BasicProperties(delivery_mode=2)
    )
    method1, _, body1 = ch.basic_get(queue=test_queue, auto_ack=True)
    assert method1 is not None
    assert json.loads(body1)["event_type"] == "InventoryReserved"
    assert json.loads(body1)["correlation_id"] == "corr-10"

    # 2. Matching routing key: "inventory.rejected"
    event_rej = Event(
        event_type="InventoryRejected",
        correlation_id="corr-11",
        payload={"order_id": 11, "reason": "Insufficient stock"}
    )
    ch.basic_publish(
        exchange=INVENTORY_EXCHANGE,
        routing_key="inventory.rejected",
        body=json.dumps(event_rej.to_dict()),
        properties=pika.BasicProperties(delivery_mode=2)
    )
    method2, _, body2 = ch.basic_get(queue=test_queue, auto_ack=True)
    assert method2 is not None
    assert json.loads(body2)["event_type"] == "InventoryRejected"
    assert json.loads(body2)["correlation_id"] == "corr-11"

    # 3. Non-matching routing key: "payment.completed"
    ch.basic_publish(
        exchange=INVENTORY_EXCHANGE,
        routing_key="payment.completed",
        body=json.dumps({"event_type": "PaymentCompleted", "payload": {"order_id": 12}}),
        properties=pika.BasicProperties(delivery_mode=2)
    )
    method3, _, _ = ch.basic_get(queue=test_queue, auto_ack=True)
    assert method3 is None

    ch.queue_delete(queue=test_queue)
    conn.close()


def test_payment_exchange_topic_routing():
    conn = get_connection()
    ch = conn.channel()

    ch.exchange_declare(exchange=PAYMENT_EXCHANGE, exchange_type="topic", durable=True)

    test_queue = "test-payment-routing-queue"
    ch.queue_declare(queue=test_queue, durable=True)
    ch.queue_bind(exchange=PAYMENT_EXCHANGE, queue=test_queue, routing_key="payment.*")
    ch.queue_purge(queue=test_queue)

    # 1. Matching routing key: "payment.completed"
    event_comp = Event(
        event_type="PaymentCompleted",
        correlation_id="corr-pay-comp",
        payload={"order_id": 20, "amount": 100.0}
    )
    ch.basic_publish(
        exchange=PAYMENT_EXCHANGE,
        routing_key="payment.completed",
        body=json.dumps(event_comp.to_dict()),
        properties=pika.BasicProperties(delivery_mode=2)
    )
    method1, _, body1 = ch.basic_get(queue=test_queue, auto_ack=True)
    assert method1 is not None
    assert json.loads(body1)["event_type"] == "PaymentCompleted"

    # 2. Matching routing key: "payment.failed"
    event_fail = Event(
        event_type="PaymentFailed",
        correlation_id="corr-pay-fail",
        payload={"order_id": 21, "reason": "Declined"}
    )
    ch.basic_publish(
        exchange=PAYMENT_EXCHANGE,
        routing_key="payment.failed",
        body=json.dumps(event_fail.to_dict()),
        properties=pika.BasicProperties(delivery_mode=2)
    )
    method2, _, body2 = ch.basic_get(queue=test_queue, auto_ack=True)
    assert method2 is not None
    assert json.loads(body2)["event_type"] == "PaymentFailed"

    # 3. Non-matching routing key: "shipping.dispatched"
    ch.basic_publish(
        exchange=PAYMENT_EXCHANGE,
        routing_key="shipping.dispatched",
        body=json.dumps({"event_type": "ShippingDispatched", "payload": {"order_id": 22}}),
        properties=pika.BasicProperties(delivery_mode=2)
    )
    method3, _, _ = ch.basic_get(queue=test_queue, auto_ack=True)
    assert method3 is None

    ch.queue_delete(queue=test_queue)
    conn.close()


def test_order_creation_publishes_event_to_queue(client):
    _, auth_headers = register_and_login(client, "messaging-envelope@example.com")

    prod_res = client.post(
        "/products/",
        json={
            "name": "Messaging Envelope Phone",
            "description": "Phone for event envelope test",
            "price": 800,
            "quantity": 5
        }
    )
    product_id = prod_res.json()["id"]

    with patch("app.services.order_service.publish_order_created") as mock_publish:
        order_res = client.post(
            "/orders/",
            json={"items": [{"product_id": product_id, "quantity": 2}]},
            headers=auth_headers | {"Idempotency-Key": "messaging-envelope-key-1"}
        )
        assert order_res.status_code == 201
        order_data = order_res.json()

        mock_publish.assert_called_once_with(
            {
                "event_id": ANY,
                "event_type": "OrderCreated",
                "occurred_at": ANY,
                "correlation_id": ANY,
                "payload": {
                    "order_id": order_data["id"],
                    "customer_id": order_data["customer_id"],
                    "total_amount": order_data["total_amount"],
                    "items": [{"product_id": product_id, "quantity": 2}]
                }
            }
        )
