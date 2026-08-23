import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def create_correlation_id() -> str:

    return str(uuid.uuid4())


@dataclass
class Event:

    event_type: str
    payload: dict[str, Any]
    correlation_id: str = field(default_factory=create_correlation_id)
    event_id: str = field(
        default_factory=lambda: str(uuid.uuid4())
    )
    occurred_at: str = field(
        default_factory=lambda: datetime.now(
            timezone.utc
        ).isoformat()
    )

    def to_dict(self):

        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "occurred_at": self.occurred_at,
            "correlation_id": self.correlation_id,
            "payload": self.payload
        }
