from datetime import datetime, timezone
from typing import Any, Optional
from pydantic import BaseModel, Field
import uuid


class BaseEvent(BaseModel):
    event_id: str
    event_type: str
    occurred_at: Optional[str] = None
    correlation_id: Optional[str] = None
    payload: dict[str, Any] = Field(default_factory=dict)


class IngestedBronzeEvent(BaseModel):
    ingestion_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    ingested_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    source_exchange: str
    source_routing_key: str
    event_id: str
    event_type: str
    occurred_at: str
    correlation_id: str
    payload: dict[str, Any]
