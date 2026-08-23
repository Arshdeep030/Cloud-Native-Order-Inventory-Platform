from unittest.mock import patch, ANY

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from services.inventory.database import Base
from services.inventory.models import Inventory, InventoryReservation, ProcessedEvent
from services.inventory.repository import (
    create_inventory,
    get_inventory,
    event_already_processed,
    get_reservations_for_order,
)
from services.inventory.consumer import handle_order_created, handle_payment_failed


@pytest.fixture
def inv_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()


def test_sufficient_inventory_reserves_and_publishes_success(inv_db):
    create_inventory(inv_db, product_id=1, quantity=100)

    event = {
        "event_id": "evt-101",
        "event_type": "OrderCreated",
        "correlation_id": "corr-xyz-101",
        "payload": {
            "order_id": 101,
            "total_amount": 250.0,
            "items": [
                {"product_id": 1, "quantity": 2}
            ]
        }
    }

    with patch("services.inventory.consumer.publish_inventory_event") as mock_publish:
        result = handle_order_created(event, inv_db)
        assert result is True

        mock_publish.assert_called_once_with(
            "inventory.reserved",
            {
                "event_id": ANY,
                "event_type": "InventoryReserved",
                "occurred_at": ANY,
                "correlation_id": "corr-xyz-101",
                "payload": {
                    "order_id": 101,
                    "amount": 250.0,
                    "items": [{"product_id": 1, "quantity": 2}]
                }
            }
        )

    inv = get_inventory(inv_db, product_id=1)
    assert inv.quantity == 100
    assert inv.reserved_quantity == 2
    assert event_already_processed(inv_db, "evt-101") is True

    reservations = get_reservations_for_order(inv_db, 101)
    assert len(reservations) == 1
    assert reservations[0].status == "RESERVED"


def test_payment_failed_triggers_compensating_inventory_release(inv_db):
    create_inventory(inv_db, product_id=1, quantity=100)

    # 1. First reserve inventory for order 101
    reserve_event = {
        "event_id": "evt-res-1",
        "event_type": "OrderCreated",
        "correlation_id": "corr-saga-1",
        "payload": {
            "order_id": 101,
            "total_amount": 300.0,
            "items": [{"product_id": 1, "quantity": 3}]
        }
    }
    with patch("services.inventory.consumer.publish_inventory_event"):
        handle_order_created(reserve_event, inv_db)

    inv = get_inventory(inv_db, product_id=1)
    assert inv.reserved_quantity == 3

    # 2. Payment fails -> Compensating transaction
    fail_event = {
        "event_id": "evt-pay-fail-compensate",
        "event_type": "PaymentFailed",
        "correlation_id": "corr-saga-1",
        "payload": {
            "order_id": 101,
            "reason": "Payment declined"
        }
    }

    with patch("services.inventory.consumer.publish_inventory_event") as mock_publish:
        result = handle_payment_failed(fail_event, inv_db)
        assert result is True

        mock_publish.assert_called_once_with(
            "inventory.released",
            {
                "event_id": ANY,
                "event_type": "InventoryReleased",
                "occurred_at": ANY,
                "correlation_id": "corr-saga-1",
                "payload": {
                    "order_id": 101
                }
            }
        )

    # Inventory reserved quantity must be rolled back to 0
    inv = get_inventory(inv_db, product_id=1)
    assert inv.reserved_quantity == 0

    reservations = get_reservations_for_order(inv_db, 101)
    assert reservations[0].status == "RELEASED"
    assert event_already_processed(inv_db, "evt-pay-fail-compensate") is True


def test_duplicate_event_is_ignored_and_not_reserved_again(inv_db):
    create_inventory(inv_db, product_id=1, quantity=100)

    event = {
        "event_id": "evt-dup-1",
        "event_type": "OrderCreated",
        "correlation_id": "corr-dup-1",
        "payload": {
            "order_id": 101,
            "items": [
                {"product_id": 1, "quantity": 2}
            ]
        }
    }

    # 1. First execution
    with patch("services.inventory.consumer.publish_inventory_event") as mock_publish:
        handle_order_created(event, inv_db)
        assert mock_publish.call_count == 1

    inv = get_inventory(inv_db, product_id=1)
    assert inv.reserved_quantity == 2
    assert inv_db.query(ProcessedEvent).count() == 1

    # 2. Second execution (duplicate message redelivery)
    with patch("services.inventory.consumer.publish_inventory_event") as mock_publish:
        handle_order_created(event, inv_db)
        assert mock_publish.call_count == 0

    inv = get_inventory(inv_db, product_id=1)
    assert inv.reserved_quantity == 2
    assert inv_db.query(ProcessedEvent).count() == 1


def test_two_different_events_both_processed(inv_db):
    create_inventory(inv_db, product_id=1, quantity=100)

    event1 = {
        "event_id": "evt-diff-1",
        "event_type": "OrderCreated",
        "correlation_id": "corr-diff-1",
        "payload": {
            "order_id": 101,
            "items": [{"product_id": 1, "quantity": 2}]
        }
    }
    event2 = {
        "event_id": "evt-diff-2",
        "event_type": "OrderCreated",
        "correlation_id": "corr-diff-2",
        "payload": {
            "order_id": 102,
            "items": [{"product_id": 1, "quantity": 3}]
        }
    }

    with patch("services.inventory.consumer.publish_inventory_event"):
        handle_order_created(event1, inv_db)
        handle_order_created(event2, inv_db)

    inv = get_inventory(inv_db, product_id=1)
    assert inv.reserved_quantity == 5
    assert inv_db.query(ProcessedEvent).count() == 2


def test_insufficient_inventory_rejects_and_publishes_failure(inv_db):
    create_inventory(inv_db, product_id=1, quantity=5)
    inv = get_inventory(inv_db, product_id=1)
    inv.reserved_quantity = 5
    inv_db.commit()

    event = {
        "event_id": "evt-reject-1",
        "event_type": "OrderCreated",
        "correlation_id": "corr-reject-1",
        "payload": {
            "order_id": 102,
            "items": [
                {"product_id": 1, "quantity": 1}
            ]
        }
    }

    with patch("services.inventory.consumer.publish_inventory_event") as mock_publish:
        result = handle_order_created(event, inv_db)
        assert result is False

        mock_publish.assert_called_once_with(
            "inventory.rejected",
            {
                "event_id": ANY,
                "event_type": "InventoryRejected",
                "occurred_at": ANY,
                "correlation_id": "corr-reject-1",
                "payload": {
                    "order_id": 102,
                    "reason": "Insufficient inventory for product 1"
                }
            }
        )

    inv = get_inventory(inv_db, product_id=1)
    assert inv.reserved_quantity == 5
    assert event_already_processed(inv_db, "evt-reject-1") is True


def test_missing_product_rejects_and_publishes_failure(inv_db):
    event = {
        "event_id": "evt-missing-1",
        "event_type": "OrderCreated",
        "correlation_id": "corr-missing-1",
        "payload": {
            "order_id": 103,
            "items": [
                {"product_id": 999, "quantity": 1}
            ]
        }
    }

    with patch("services.inventory.consumer.publish_inventory_event") as mock_publish:
        result = handle_order_created(event, inv_db)
        assert result is False

        mock_publish.assert_called_once_with(
            "inventory.rejected",
            {
                "event_id": ANY,
                "event_type": "InventoryRejected",
                "occurred_at": ANY,
                "correlation_id": "corr-missing-1",
                "payload": {
                    "order_id": 103,
                    "reason": "Inventory not found for product 999"
                }
            }
        )
    assert event_already_processed(inv_db, "evt-missing-1") is True


def test_multiple_items_reserves_all(inv_db):
    create_inventory(inv_db, product_id=1, quantity=50)
    create_inventory(inv_db, product_id=2, quantity=30)

    event = {
        "event_id": "evt-multi-1",
        "event_type": "OrderCreated",
        "correlation_id": "corr-multi-1",
        "payload": {
            "order_id": 104,
            "items": [
                {"product_id": 1, "quantity": 2},
                {"product_id": 2, "quantity": 3}
            ]
        }
    }

    with patch("services.inventory.consumer.publish_inventory_event") as mock_publish:
        result = handle_order_created(event, inv_db)
        assert result is True

        mock_publish.assert_called_once_with(
            "inventory.reserved",
            {
                "event_id": ANY,
                "event_type": "InventoryReserved",
                "occurred_at": ANY,
                "correlation_id": "corr-multi-1",
                "payload": {
                    "order_id": 104,
                    "amount": 0.0,
                    "items": [
                        {"product_id": 1, "quantity": 2},
                        {"product_id": 2, "quantity": 3}
                    ]
                }
            }
        )

    inv1 = get_inventory(inv_db, product_id=1)
    inv2 = get_inventory(inv_db, product_id=2)
    assert inv1.reserved_quantity == 2
    assert inv2.reserved_quantity == 3
    assert event_already_processed(inv_db, "evt-multi-1") is True


def test_partial_failure_rejects_all_and_preserves_atomicity(inv_db):
    create_inventory(inv_db, product_id=1, quantity=10)
    create_inventory(inv_db, product_id=2, quantity=2)

    event = {
        "event_id": "evt-partial-1",
        "event_type": "OrderCreated",
        "correlation_id": "corr-partial-1",
        "payload": {
            "order_id": 105,
            "items": [
                {"product_id": 1, "quantity": 2},  # Available (10 >= 2)
                {"product_id": 2, "quantity": 5}   # Unavailable (2 < 5)
            ]
        }
    }

    with patch("services.inventory.consumer.publish_inventory_event") as mock_publish:
        result = handle_order_created(event, inv_db)
        assert result is False

        mock_publish.assert_called_once_with(
            "inventory.rejected",
            {
                "event_id": ANY,
                "event_type": "InventoryRejected",
                "occurred_at": ANY,
                "correlation_id": "corr-partial-1",
                "payload": {
                    "order_id": 105,
                    "reason": "Insufficient inventory for product 2"
                }
            }
        )

    # Assert NEITHER item was reserved
    inv1 = get_inventory(inv_db, product_id=1)
    inv2 = get_inventory(inv_db, product_id=2)
    assert inv1.reserved_quantity == 0
    assert inv2.reserved_quantity == 0
    assert event_already_processed(inv_db, "evt-partial-1") is True
