from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db


router = APIRouter(
    prefix="/health",
    tags=["Health"]
)


@router.get("/live")
def liveness_check():

    return {
        "status": "alive"
    }


@router.get("/ready")
def readiness_check(
    db: Session = Depends(get_db)
):

    db.execute(text("SELECT 1"))

    return {
        "status": "ready"
    }
