import json
import os
import shutil
import tempfile
import uuid
from pathlib import Path

import pytest
from pydantic import ValidationError

from data_ingestion.schemas.base import BaseEvent, IngestedBronzeEvent
from data_ingestion.schemas.order import OrderCreatedPayload, OrderItemSchema
from data_ingestion.schemas.inventory import (
    InventoryReservedPayload,
    InventoryRejectedPayload,
    InventoryReleasedPayload,
)
from data_ingestion.schemas.payment import (
    PaymentCompletedPayload,
    PaymentFailedPayload,
)
from data_ingestion.writers.bronze_writer import BronzeDataLakeWriter
from data_ingestion.consumer import DataLakeIngestionConsumer


@pytest.fixture
def temp_lake_dir():
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_order_created_schema_valid():
    payload = {
        "order_id": 101,
        "customer_id": 1,
        "total_amount": 199.98,
        "items": [{"product_id": 1, "quantity": 2, "unit_price": 99.99}],
    }
    schema = OrderCreatedPayload(**payload)
    assert schema.order_id == 101
    assert len(schema.items) == 1
    assert schema.items[0].quantity == 2


def test_order_created_schema_invalid_quantity():
    payload = {
        "order_id": 101,
        "customer_id": 1,
        "total_amount": 199.98,
        "items": [{"product_id": 1, "quantity": 0, "unit_price": 99.99}],
    }
    with pytest.raises(ValidationError):
        OrderCreatedPayload(**payload)


def test_inventory_schemas():
    reserved = InventoryReservedPayload(
        order_id=101,
        amount=199.98,
        items=[{"product_id": 1, "quantity": 2}],
    )
    assert reserved.order_id == 101

    rejected = InventoryRejectedPayload(order_id=102, reason="Out of stock")
    assert rejected.reason == "Out of stock"

    released = InventoryReleasedPayload(order_id=103)
    assert released.order_id == 103


def test_payment_schemas():
    completed = PaymentCompletedPayload(
        order_id=101,
        payment_id=501,
        amount=199.98,
    )
    assert completed.order_id == 101
    assert completed.payment_id == 501
    assert completed.amount == 199.98

    failed = PaymentFailedPayload(
        order_id=102,
        amount=9999.00,
        reason="Insufficient funds",
    )
    assert failed.order_id == 102
    assert failed.reason == "Insufficient funds"



def test_bronze_data_lake_writer(temp_lake_dir):
    writer = BronzeDataLakeWriter(base_path=temp_lake_dir)

    event_id = str(uuid.uuid4())
    event = IngestedBronzeEvent(
        source_exchange="order-events",
        source_routing_key="order.created",
        event_id=event_id,
        event_type="OrderCreated",
        occurred_at="2026-08-24T12:30:00+00:00",
        correlation_id=str(uuid.uuid4()),
        payload={"order_id": 101, "total_amount": 199.99},
    )

    saved_file = writer.write_event(event)

    # Check file exists in year/month/day partitioned directory
    assert os.path.exists(saved_file)
    assert "orders" in saved_file
    assert "year=2026" in saved_file
    assert "month=08" in saved_file
    assert "day=24" in saved_file

    with open(saved_file, "r") as f:
        data = json.load(f)
    assert data["event_id"] == event_id
    assert data["event_type"] == "OrderCreated"

    # Check jsonl partition log exists
    jsonl_file = Path(saved_file).parent / "events.jsonl"
    assert jsonl_file.exists()
    with open(jsonl_file, "r") as f:
        lines = f.readlines()
    assert len(lines) == 1


def test_consumer_process_message(temp_lake_dir):
    writer = BronzeDataLakeWriter(base_path=temp_lake_dir)
    consumer = DataLakeIngestionConsumer(writer=writer)

    event_id = str(uuid.uuid4())
    raw_event = {
        "event_id": event_id,
        "event_type": "PaymentCompleted",
        "occurred_at": "2026-08-24T14:15:00Z",
        "correlation_id": str(uuid.uuid4()),
        "payload": {"order_id": 5, "payment_id": 1, "amount": 1999.99},
    }

    body = json.dumps(raw_event).encode("utf-8")
    ingested = consumer.process_message(
        body=body,
        exchange="payment-events",
        routing_key="payment.completed",
    )

    assert ingested.event_id == event_id
    assert ingested.event_type == "PaymentCompleted"
    assert ingested.source_exchange == "payment-events"
    assert ingested.source_routing_key == "payment.completed"

    expected_file = (
        Path(temp_lake_dir)
        / "payments"
        / "year=2026"
        / "month=08"
        / "day=24"
        / f"{event_id}.json"
    )
    assert expected_file.exists()
