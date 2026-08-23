from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy import Float
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy.sql import func

try:
    from database import Base
except ImportError:
    from services.payment.database import Base


class Payment(Base):

    __tablename__ = "payments"

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

    amount = Column(
        Float,
        nullable=False
    )

    status = Column(
        String,
        nullable=False,
        default="PENDING"  # "PENDING", "COMPLETED", "FAILED"
    )

    created_at = Column(
        DateTime,
        server_default=func.now()
    )

    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now()
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
