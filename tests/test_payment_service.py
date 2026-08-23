from unittest.mock import patch, ANY

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from services.payment.database import Base
from services.payment.models import Payment, ProcessedEvent
from services.payment.repository import (
    create_payment,
    get_payment_by_order_id,
    event_already_processed,
)
from services.payment.consumer import handle_inventory_reserved


@pytest.fixture
def pay_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()


def test_payment_creation_and_retrieval(pay_db):
    payment = create_payment(pay_db, order_id=1, amount=150.0, status="COMPLETED")
    assert payment.id is not None
    assert payment.order_id == 1
    assert payment.amount == 150.0
    assert payment.status == "COMPLETED"

    fetched = get_payment_by_order_id(pay_db, order_id=1)
    assert fetched is not None
    assert fetched.amount == 150.0
    assert fetched.status == "COMPLETED"


def test_inventory_reserved_processes_payment_success_and_publishes(pay_db):
    event = {
        "event_id": "evt-pay-101",
        "event_type": "InventoryReserved",
        "correlation_id": "corr-pay-101",
        "payload": {
            "order_id": 101,
            "amount": 250.0
        }
    }

    with patch("services.payment.consumer.publish_payment_event") as mock_publish:
        result = handle_inventory_reserved(event, pay_db)
        assert result is True

        mock_publish.assert_called_once_with(
            "payment.completed",
            {
                "event_id": ANY,
                "event_type": "PaymentCompleted",
                "occurred_at": ANY,
                "correlation_id": "corr-pay-101",
                "payload": {
                    "order_id": 101,
                    "payment_id": ANY,
                    "amount": 250.0
                }
            }
        )

    payment = get_payment_by_order_id(pay_db, 101)
    assert payment is not None
    assert payment.status == "COMPLETED"
    assert payment.amount == 250.0
    assert event_already_processed(pay_db, "evt-pay-101") is True


def test_inventory_reserved_processes_payment_failure_and_publishes(pay_db):
    event = {
        "event_id": "evt-pay-fail-1",
        "event_type": "InventoryReserved",
        "correlation_id": "corr-pay-fail-1",
        "payload": {
            "order_id": 102,
            "amount": 9999.0  # Sentinel failure trigger
        }
    }

    with patch("services.payment.consumer.publish_payment_event") as mock_publish:
        result = handle_inventory_reserved(event, pay_db)
        assert result is False

        mock_publish.assert_called_once_with(
            "payment.failed",
            {
                "event_id": ANY,
                "event_type": "PaymentFailed",
                "occurred_at": ANY,
                "correlation_id": "corr-pay-fail-1",
                "payload": {
                    "order_id": 102,
                    "payment_id": ANY,
                    "amount": 9999.0,
                    "reason": "Payment declined"
                }
            }
        )

    payment = get_payment_by_order_id(pay_db, 102)
    assert payment is not None
    assert payment.status == "FAILED"
    assert event_already_processed(pay_db, "evt-pay-fail-1") is True


def test_duplicate_payment_event_is_ignored_and_not_processed_again(pay_db):
    event = {
        "event_id": "evt-dup-pay-1",
        "event_type": "InventoryReserved",
        "correlation_id": "corr-dup-pay-1",
        "payload": {
            "order_id": 103,
            "amount": 300.0
        }
    }

    # 1. First execution
    with patch("services.payment.consumer.publish_payment_event") as mock_publish:
        handle_inventory_reserved(event, pay_db)
        assert mock_publish.call_count == 1

    assert pay_db.query(Payment).filter(Payment.order_id == 103).count() == 1
    assert pay_db.query(ProcessedEvent).count() == 1

    # 2. Second execution (duplicate message redelivery)
    with patch("services.payment.consumer.publish_payment_event") as mock_publish:
        handle_inventory_reserved(event, pay_db)
        assert mock_publish.call_count == 0

    assert pay_db.query(Payment).filter(Payment.order_id == 103).count() == 1
    assert pay_db.query(ProcessedEvent).count() == 1


def test_two_different_payment_events_both_processed(pay_db):
    event1 = {
        "event_id": "evt-diff-pay-1",
        "event_type": "InventoryReserved",
        "correlation_id": "corr-diff-pay-1",
        "payload": {"order_id": 104, "amount": 100.0}
    }
    event2 = {
        "event_id": "evt-diff-pay-2",
        "event_type": "InventoryReserved",
        "correlation_id": "corr-diff-pay-2",
        "payload": {"order_id": 105, "amount": 200.0}
    }

    with patch("services.payment.consumer.publish_payment_event"):
        handle_inventory_reserved(event1, pay_db)
        handle_inventory_reserved(event2, pay_db)

    assert pay_db.query(Payment).count() == 2
    assert pay_db.query(ProcessedEvent).count() == 2
