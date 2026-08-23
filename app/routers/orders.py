from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.order_schema import OrderCreate, OrderResponse
from app.services.order_service import order_service

from app.security.dependencies import get_current_user
from app.models.user import User

router = APIRouter(
    prefix="/orders",
    tags=["Orders"]
)


@router.post(
    "/",
    response_model=OrderResponse,
    status_code=201
)
def create_order(
    order_data: OrderCreate,
    idempotency_key: str = Header(...),
    x_correlation_id: str | None = Header(None, alias="X-Correlation-ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):

    return order_service.create_order(
        db,
        order_data,
        current_user.id,
        idempotency_key,
        correlation_id=x_correlation_id
    )


@router.get("/{order_id}", response_model=OrderResponse)
def get_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    order = order_service.get_order(db, order_id)

    if order.customer_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="Not authorized to access this order"
        )

    return order
