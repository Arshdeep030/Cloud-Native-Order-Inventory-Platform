from app.models import Order, User, ProcessedEvent
from app.messaging.order_consumer import process_order_workflow_event
from app.repositories.order_repository import order_repository
from app.repositories.processed_event_repository import event_already_processed


def create_test_order(db_session, email="worker_test@example.com", status="PENDING"):
    user = User(email=email, password_hash="pw", role="customer")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    order = Order(customer_id=user.id, status=status, total_amount=100.0)
    db_session.add(order)
    db_session.commit()
    db_session.refresh(order)
    return order


def test_inventory_reserved_updates_order_status_to_payment_pending(db_session):
    order = create_test_order(db_session, email="worker_reserved@example.com")
    assert order.status == "PENDING"

    event = {
        "event_id": "order-worker-evt-1",
        "event_type": "InventoryReserved",
        "correlation_id": "corr-worker-1",
        "payload": {
            "order_id": order.id
        }
    }

    process_order_workflow_event(event, db_session)

    updated_order = order_repository.get_order(db_session, order.id)
    assert updated_order.status == "PAYMENT_PENDING"
    assert event_already_processed(db_session, "order-worker-evt-1") is True


def test_payment_completed_updates_order_status_to_confirmed(db_session):
    order = create_test_order(db_session, email="worker_pay_comp@example.com", status="PAYMENT_PENDING")

    event = {
        "event_id": "order-worker-evt-pay-comp",
        "event_type": "PaymentCompleted",
        "correlation_id": "corr-worker-pay-comp",
        "payload": {
            "order_id": order.id,
            "payment_id": 1,
            "amount": 100.0
        }
    }

    process_order_workflow_event(event, db_session)

    updated_order = order_repository.get_order(db_session, order.id)
    assert updated_order.status == "CONFIRMED"
    assert event_already_processed(db_session, "order-worker-evt-pay-comp") is True


def test_payment_failed_updates_order_status_to_cancelled(db_session):
    order = create_test_order(db_session, email="worker_pay_fail@example.com", status="PAYMENT_PENDING")

    event = {
        "event_id": "order-worker-evt-pay-fail",
        "event_type": "PaymentFailed",
        "correlation_id": "corr-worker-pay-fail",
        "payload": {
            "order_id": order.id,
            "payment_id": 2,
            "amount": 100.0,
            "reason": "Payment declined"
        }
    }

    process_order_workflow_event(event, db_session)

    updated_order = order_repository.get_order(db_session, order.id)
    assert updated_order.status == "CANCELLED"
    assert event_already_processed(db_session, "order-worker-evt-pay-fail") is True


def test_inventory_rejected_updates_order_status_to_cancelled(db_session):
    order = create_test_order(db_session, email="worker_rejected@example.com")
    assert order.status == "PENDING"

    event = {
        "event_id": "order-worker-evt-2",
        "event_type": "InventoryRejected",
        "correlation_id": "corr-worker-2",
        "payload": {
            "order_id": order.id,
            "reason": "Insufficient stock"
        }
    }

    process_order_workflow_event(event, db_session)

    updated_order = order_repository.get_order(db_session, order.id)
    assert updated_order.status == "CANCELLED"
    assert event_already_processed(db_session, "order-worker-evt-2") is True


def test_unknown_event_does_not_crash(db_session):
    order = create_test_order(db_session, email="worker_unknown@example.com")

    event = {
        "event_id": "order-worker-evt-3",
        "event_type": "SomethingHappened",
        "correlation_id": "corr-worker-3",
        "payload": {
            "order_id": order.id
        }
    }

    # Should not raise exception
    process_order_workflow_event(event, db_session)

    updated_order = order_repository.get_order(db_session, order.id)
    assert updated_order.status == "PENDING"


def test_missing_order_handled_safely(db_session):
    event = {
        "event_id": "order-worker-evt-4",
        "event_type": "PaymentCompleted",
        "correlation_id": "corr-worker-4",
        "payload": {
            "order_id": 999999
        }
    }

    # Should not raise exception
    process_order_workflow_event(event, db_session)


def test_duplicate_payment_completed_event(db_session):
    order = create_test_order(db_session, email="worker_dup_pay@example.com", status="PAYMENT_PENDING")

    event = {
        "event_id": "order-worker-evt-dup-pay",
        "event_type": "PaymentCompleted",
        "correlation_id": "corr-worker-dup-pay",
        "payload": {
            "order_id": order.id,
            "amount": 100.0
        }
    }

    # Process first time
    process_order_workflow_event(event, db_session)
    updated_order = order_repository.get_order(db_session, order.id)
    assert updated_order.status == "CONFIRMED"
    assert db_session.query(ProcessedEvent).filter(ProcessedEvent.event_id == "order-worker-evt-dup-pay").count() == 1

    # Process second time (duplicate delivery)
    process_order_workflow_event(event, db_session)
    updated_order = order_repository.get_order(db_session, order.id)
    assert updated_order.status == "CONFIRMED"
    assert db_session.query(ProcessedEvent).filter(ProcessedEvent.event_id == "order-worker-evt-dup-pay").count() == 1


def test_two_different_event_ids_both_recorded(db_session):
    order1 = create_test_order(db_session, email="worker_diff_1@example.com")
    order2 = create_test_order(db_session, email="worker_diff_2@example.com")

    event1 = {
        "event_id": "order-worker-evt-diff-1",
        "event_type": "PaymentCompleted",
        "correlation_id": "corr-worker-diff-1",
        "payload": {
            "order_id": order1.id
        }
    }
    event2 = {
        "event_id": "order-worker-evt-diff-2",
        "event_type": "PaymentCompleted",
        "correlation_id": "corr-worker-diff-2",
        "payload": {
            "order_id": order2.id
        }
    }

    process_order_workflow_event(event1, db_session)
    process_order_workflow_event(event2, db_session)

    assert event_already_processed(db_session, "order-worker-evt-diff-1") is True
    assert event_already_processed(db_session, "order-worker-evt-diff-2") is True
