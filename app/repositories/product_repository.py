from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Product


class ProductRepository:

    def get_products(
        self,
        db: Session
    ):
        statement = select(Product)

        return db.scalars(statement).all()

    def get_product(
        self,
        db: Session,
        product_id: int
    ) -> Product | None:

        statement = select(Product).where(
            Product.id == product_id
        )

        return db.scalars(statement).first()

    def get_product_for_update(
        self,
        db: Session,
        product_id: int
    ) -> Product | None:
        statement = (
            select(Product)
            .where(Product.id == product_id)
            .with_for_update()
        )

        return db.scalars(statement).first()

    def create_product(
        self,
        db: Session,
        product: Product
    ) -> Product:

        db.add(product)
        db.commit()
        db.refresh(product)

        return product

    def delete_product(
        self,
        db: Session,
        product: Product
    ):

        db.delete(product)
        db.commit()

    def update_product(
        self,
        db: Session,
        product: Product
    ) -> Product:

        db.commit()
        db.refresh(product)

        return product

    def update_quantity(
        self,
        db: Session,
        product: Product,
        quantity: int
    ) -> Product:

        product.quantity = quantity

        db.flush()

        return product


product_repository = ProductRepository()
