from sqlalchemy import Column, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database import Base


class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"
    __table_args__ = (
        UniqueConstraint(
            "customer_id",
            "key",
            name="uq_idempotency_keys_customer_key"
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, nullable=False, index=True)
    customer_id = Column(Integer, nullable=False, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)

    order = relationship("Order")
