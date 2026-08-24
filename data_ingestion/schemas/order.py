from typing import List
from pydantic import BaseModel, Field


class OrderItemSchema(BaseModel):
    product_id: int
    quantity: int = Field(gt=0)
    unit_price: float = Field(ge=0)


class OrderCreatedPayload(BaseModel):
    order_id: int
    customer_id: int
    total_amount: float = Field(ge=0)
    items: List[OrderItemSchema] = Field(default_factory=list)
