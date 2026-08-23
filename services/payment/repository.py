from sqlalchemy.orm import Session

try:
    from models import Payment, ProcessedEvent
except ImportError:
    from services.payment.models import Payment, ProcessedEvent


def get_payment_by_order_id(
    db: Session,
    order_id: int
) -> Payment | None:

    return (
        db.query(Payment)
        .filter(Payment.order_id == order_id)
        .first()
    )


def create_payment(
    db: Session,
    order_id: int,
    amount: float,
    status: str = "PENDING"
) -> Payment:

    payment = Payment(
        order_id=order_id,
        amount=amount,
        status=status
    )

    db.add(payment)
    db.flush()

    return payment


def update_payment_status(
    db: Session,
    payment_id: int,
    status: str
) -> Payment | None:

    payment = (
        db.query(Payment)
        .filter(Payment.id == payment_id)
        .first()
    )

    if not payment:
        return None

    payment.status = status
    db.flush()

    return payment


def event_already_processed(
    db: Session,
    event_id: str
) -> bool:

    event = (
        db.query(ProcessedEvent)
        .filter(ProcessedEvent.event_id == event_id)
        .first()
    )

    return event is not None


def mark_event_processed(
    db: Session,
    event_id: str
):

    processed_event = ProcessedEvent(
        event_id=event_id
    )

    db.add(processed_event)
