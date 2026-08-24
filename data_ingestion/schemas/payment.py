from typing import Optional
from pydantic import BaseModel, Field


class PaymentCompletedPayload(BaseModel):
    order_id: int
    payment_id: int
    amount: float = Field(ge=0)


class PaymentFailedPayload(BaseModel):
    order_id: int
    payment_id: Optional[int] = None
    amount: float = Field(ge=0)
    reason: Optional[str] = "Payment declined"
