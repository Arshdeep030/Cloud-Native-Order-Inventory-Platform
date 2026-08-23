from sqlalchemy.orm import Session

from app.models import Product
from app.exceptions import ProductNotFoundError
from app.schemas import ProductCreate, ProductUpdate

from app.repositories.product_repository import product_repository
from app.repositories.cache_repository import cache_repository


class ProductService:

    def get_products(
        self,
        db: Session
    ):
        return product_repository.get_products(db)

    def get_product(
        self,
        db: Session,
        product_id: int
    ):
        cache_key = f"product:{product_id}"

        cached_product = cache_repository.get(
            cache_key
        )

        if cached_product is not None:
            return cached_product

        product = product_repository.get_product(
            db,
            product_id
        )

        if product is None:
            raise ProductNotFoundError(product_id)

        product_data = {
            "id": product.id,
            "name": product.name,
            "description": product.description,
            "price": product.price,
            "quantity": product.quantity
        }

        cache_repository.set(
            cache_key,
            product_data
        )

        return product_data

    def create_product(
        self,
        db: Session,
        product_data: ProductCreate
    ) -> Product:

        product = Product(
            name=product_data.name,
            description=product_data.description,
            price=product_data.price,
            quantity=product_data.quantity
        )

        return product_repository.create_product(
            db,
            product
        )

    def update_product(
        self,
        db: Session,
        product_id: int,
        product_data: ProductUpdate
    ):

        product = product_repository.get_product(
            db,
            product_id
        )

        if product is None:
            raise ProductNotFoundError(product_id)

        if product_data.name is not None:
            product.name = product_data.name

        if product_data.description is not None:
            product.description = product_data.description

        if product_data.price is not None:
            product.price = product_data.price

        if product_data.quantity is not None:
            product.quantity = product_data.quantity

        updated_product = product_repository.update_product(
            db,
            product
        )

        cache_repository.delete(
            f"product:{product_id}"
        )

        return updated_product

    def delete_product(
        self,
        db: Session,
        product_id: int
    ):

        product = product_repository.get_product(
            db,
            product_id
        )

        if product is None:
            raise ProductNotFoundError(product_id)

        product_repository.delete_product(
            db,
            product
        )

        cache_repository.delete(
            f"product:{product_id}"
        )

        return product


product_service = ProductService()
