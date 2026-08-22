from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.schemas import ProductCreate, ProductUpdate
from app.models import Product
from app.repositories import product_repository
from app.schemas import ProductCreate


def get_products(db: Session):
    return product_repository.get_products(db)


def get_product(db: Session, product_id: int):
    product = product_repository.get_product(db, product_id)

    if product is None:
        raise HTTPException(
            status_code=404,
            detail="Product not found"
        )

    return product


def create_product(db: Session, product_data: ProductCreate):

    product = Product(
        name=product_data.name,
        description=product_data.description,
        price=product_data.price,
        quantity=product_data.quantity
    )

    return product_repository.create_product(db, product)


def delete_product(db: Session, product_id: int):

    product = get_product(db, product_id)

    product_repository.delete_product(db, product)

    return {"message": "Product deleted successfully"}

def update_product(
    db: Session,
    product_id: int,
    product_data: ProductUpdate
):
    product = get_product(db, product_id)

    update_data = product_data.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(product, field, value)

    return product_repository.update_product(db, product)