from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Product


def get_products(db: Session):
    statement = select(Product)
    return db.scalars(statement).all()


def get_product(db: Session, product_id: int):
    statement = select(Product).where(Product.id == product_id)
    return db.scalars(statement).first()


def create_product(db: Session, product: Product):
    db.add(product)
    db.commit()
    db.refresh(product)

    return product


def delete_product(db: Session, product: Product):
    db.delete(product)
    db.commit()
    
def update_product(db: Session, product: Product):
    db.commit()
    db.refresh(product)

    return product