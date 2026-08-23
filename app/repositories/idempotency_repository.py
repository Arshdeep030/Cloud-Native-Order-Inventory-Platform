from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.idempotency import IdempotencyKey


class IdempotencyRepository:

    def get_by_key(
        self,
        db: Session,
        customer_id: int,
        key: str
    ) -> IdempotencyKey | None:
        statement = select(IdempotencyKey).where(
            IdempotencyKey.customer_id == customer_id,
            IdempotencyKey.key == key
        )

        return db.scalars(statement).first()

    def create(
        self,
        db: Session,
        customer_id: int,
        key: str,
        order_id: int
    ) -> IdempotencyKey:
        record = IdempotencyKey(
            customer_id=customer_id,
            key=key,
            order_id=order_id
        )

        db.add(record)
        db.flush()

        return record


idempotency_repository = IdempotencyRepository()
