from typing import List, Optional
from pydantic import BaseModel, Field


class InventoryItemSchema(BaseModel):
    product_id: int
    quantity: int = Field(gt=0)


class InventoryReservedPayload(BaseModel):
    order_id: int
    amount: float = Field(ge=0)
    items: List[dict] = Field(default_factory=list)


class InventoryRejectedPayload(BaseModel):
    order_id: int
    reason: str


class InventoryReleasedPayload(BaseModel):
    order_id: int
