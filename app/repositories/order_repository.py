from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Order, OrderItem


class OrderRepository:

    def create_order(
        self,
        db: Session,
        order: Order
    ) -> Order:

        db.add(order)
        db.flush()

        return order

    def create_order_item(
        self,
        db: Session,
        order_item: OrderItem
    ) -> OrderItem:

        db.add(order_item)
        db.flush()

        return order_item

    def get_order(
        self,
        db: Session,
        order_id: int
    ) -> Order | None:

        statement = select(Order).where(
            Order.id == order_id
        )

        return db.scalars(statement).first()

    def get_orders(
        self,
        db: Session
    ) -> list[Order]:

        statement = select(Order)

        return db.scalars(statement).all()

    def update_order_status(
        self,
        db: Session,
        order_id: int,
        status: str
    ) -> Order | None:

        order = self.get_order(db, order_id)

        if not order:
            return None

        order.status = status

        db.flush()

        return order


order_repository = OrderRepository()