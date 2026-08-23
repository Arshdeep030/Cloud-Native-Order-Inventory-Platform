from sqlalchemy.orm import Session

try:
    from models import Inventory, InventoryReservation, ProcessedEvent
except ImportError:
    from services.inventory.models import Inventory, InventoryReservation, ProcessedEvent


def get_inventory(
    db: Session,
    product_id: int
):

    return (
        db.query(Inventory)
        .filter(
            Inventory.product_id == product_id
        )
        .first()
    )


def create_inventory(
    db: Session,
    product_id: int,
    quantity: int
):

    inventory = Inventory(
        product_id=product_id,
        quantity=quantity,
        reserved_quantity=0
    )

    db.add(inventory)
    db.commit()
    db.refresh(inventory)

    return inventory


def create_reservation(
    db: Session,
    order_id: int,
    product_id: int,
    quantity: int
) -> InventoryReservation:

    reservation = InventoryReservation(
        order_id=order_id,
        product_id=product_id,
        quantity=quantity,
        status="RESERVED"
    )

    db.add(reservation)
    db.flush()

    return reservation


def get_reservations_for_order(
    db: Session,
    order_id: int
) -> list[InventoryReservation]:

    return (
        db.query(InventoryReservation)
        .filter(
            InventoryReservation.order_id == order_id
        )
        .all()
    )


def release_inventory(
    db: Session,
    order_id: int
) -> list[InventoryReservation]:

    reservations = (
        db.query(InventoryReservation)
        .filter(
            InventoryReservation.order_id == order_id,
            InventoryReservation.status == "RESERVED"
        )
        .all()
    )

    for res in reservations:
        inv = get_inventory(db, res.product_id)
        if inv:
            inv.reserved_quantity = max(0, inv.reserved_quantity - res.quantity)
        res.status = "RELEASED"

    db.flush()

    return reservations


def event_already_processed(
    db: Session,
    event_id: str
) -> bool:

    event = (
        db.query(ProcessedEvent)
        .filter(
            ProcessedEvent.event_id == event_id
        )
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
