from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import ProductCreate, ProductResponse
from app.services import product_service


router = APIRouter(
    prefix="/products",
    tags=["Products"]
)


@router.get("/", response_model=list[ProductResponse])
def get_products(db: Session = Depends(get_db)):
    return product_service.get_products(db)


@router.get("/{product_id}", response_model=ProductResponse)
def get_product(
    product_id: int,
    db: Session = Depends(get_db)
):
    return product_service.get_product(db, product_id)


@router.post("/", response_model=ProductResponse)
def create_product(
    product: ProductCreate,
    db: Session = Depends(get_db)
):
    return product_service.create_product(db, product)


@router.delete("/{product_id}")
def delete_product(
    product_id: int,
    db: Session = Depends(get_db)
):
    return product_service.delete_product(db, product_id)