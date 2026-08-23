from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy import String
from sqlalchemy.sql import func

from app.database import Base


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
