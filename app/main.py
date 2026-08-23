from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from app.middleware import request_logging_middleware
from app.exceptions import AppException
from app.routers import products, orders, auth, health
from app.database import engine, Base
import app.models
from app.logging_config import configure_logging

try:
    Base.metadata.create_all(bind=engine)
except Exception:
    pass

configure_logging()

app = FastAPI(
    title="Cloud Order Platform API",
    description=(
        "Cloud-native order processing platform "
        "built with FastAPI and PostgreSQL."
    ),
    version="1.0.0"
)
app.middleware(
    "http"
)(request_logging_middleware)

@app.exception_handler(AppException)
async def app_exception_handler(
    request: Request,
    exc: AppException
):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message
            }
        }
    )


app.include_router(health.router)
app.include_router(products.router)
app.include_router(orders.router)
app.include_router(auth.router)


@app.get("/")
def root():
    return {
        "message": "Cloud Order Platform API"
    }


@app.get("/metrics")
def metrics():
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )
