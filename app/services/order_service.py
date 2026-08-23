import logging
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Order, OrderItem, Product
from app.exceptions import (
    InsufficientInventoryError,
    OrderNotFoundError,
    ProductNotFoundError,
)
from app.order_schema import OrderCreate

from app.repositories.order_repository import order_repository
from app.repositories.product_repository import product_repository
from app.repositories.idempotency_repository import idempotency_repository
from app.repositories.cache_repository import cache_repository
from app.messaging.events import Event, create_correlation_id
from app.messaging.publisher import publish_order_created


logger = logging.getLogger(
    "cloud-order-platform.orders"
)


class OrderService:

    def create_order(
        self,
        db: Session,
        order_data: OrderCreate,
        customer_id: int,
        idempotency_key: str,
        correlation_id: str | None = None
    ) -> Order:

        try:

            existing_record = idempotency_repository.get_by_key(
                db,
                customer_id,
                idempotency_key
            )

            if existing_record is not None:
                return existing_record.order

            total_amount = 0
            products_by_id: dict[int, Product] = {}
            requested_quantities: dict[int, int] = {}

            for item in order_data.items:
                requested_quantities[item.product_id] = (
                    requested_quantities.get(item.product_id, 0)
                    + item.quantity
                )

            for product_id in sorted(requested_quantities):
                product = product_repository.get_product_for_update(
                    db,
                    product_id
                )

                if product is None:
                    raise ProductNotFoundError(product_id)

                if product.quantity < requested_quantities[product_id]:
                    logger.warning(
                        "insufficient_inventory "
                        "product_id=%s requested=%s available=%s",
                        product.id,
                        requested_quantities[product_id],
                        product.quantity
                    )
                    raise InsufficientInventoryError(product.id)

                products_by_id[product_id] = product

            for item in order_data.items:
                total_amount += products_by_id[item.product_id].price * item.quantity

            for product_id, product in products_by_id.items():
                product.quantity -= requested_quantities[product_id]

            # -----------------------------
            # 2. Create Order
            # -----------------------------

            order = Order(
                customer_id=customer_id,
                status="PENDING",
                total_amount=total_amount
            )

            order_repository.create_order(
                db,
                order
            )

            # -----------------------------
            # 3. Create Order Items
            # -----------------------------

            for item in order_data.items:
                product = products_by_id[item.product_id]

                order_item = OrderItem(
                    order_id=order.id,
                    product_id=product.id,
                    quantity=item.quantity,
                    unit_price=product.price
                )

                order_repository.create_order_item(
                    db,
                    order_item
                )

            idempotency_repository.create(
                db,
                customer_id,
                idempotency_key,
                order.id
            )

            # -----------------------------
            # 4. Commit
            # -----------------------------

            db.commit()

            db.refresh(order)

            for product_id in products_by_id:
                cache_repository.delete(f"product:{product_id}")

            items = [
                {
                    "product_id": item.product_id,
                    "quantity": item.quantity
                }
                for item in order.items
            ]

            correlation_id = correlation_id or create_correlation_id()

            event = Event(
                event_type="OrderCreated",
                correlation_id=correlation_id,
                payload={
                    "order_id": order.id,
                    "customer_id": order.customer_id,
                    "total_amount": order.total_amount,
                    "items": items
                }
            )

            publish_order_created(
                event.to_dict()
            )

            logger.info(
                "order_created order_id=%s customer_id=%s total_amount=%s correlation_id=%s",
                order.id,
                customer_id,
                order.total_amount,
                correlation_id
            )

            return order

        except IntegrityError:
            db.rollback()

            existing_record = idempotency_repository.get_by_key(
                db,
                customer_id,
                idempotency_key
            )

            if existing_record is not None:
                return existing_record.order

            raise

        except Exception:
            db.rollback()
            raise

    def get_order(
        self,
        db: Session,
        order_id: int
    ) -> Order:
        order = order_repository.get_order(db, order_id)

        if order is None:
            raise OrderNotFoundError(order_id)

        return order


order_service = OrderService()
