from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy.sql import func

try:
    from database import Base
except ImportError:
    from services.inventory.database import Base


class Inventory(Base):

    __tablename__ = "inventory"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    product_id = Column(
        Integer,
        nullable=False,
        unique=True,
        index=True
    )

    quantity = Column(
        Integer,
        nullable=False,
        default=0
    )

    reserved_quantity = Column(
        Integer,
        nullable=False,
        default=0
    )


class InventoryReservation(Base):

    __tablename__ = "inventory_reservations"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    order_id = Column(
        Integer,
        nullable=False,
        index=True
    )

    product_id = Column(
        Integer,
        nullable=False,
        index=True
    )

    quantity = Column(
        Integer,
        nullable=False
    )

    status = Column(
        String,
        nullable=False,
        default="RESERVED"  # "RESERVED" or "RELEASED"
    )

    created_at = Column(
        DateTime,
        server_default=func.now()
    )


class ProcessedEvent(Base):

    __tablename__ = "processed_events"

    event_id = Column(
        String,
        primary_key=True,
        index=True
    )

    processed_at = Column(
        DateTime,
        server_default=func.now(),
        nullable=False
    )
