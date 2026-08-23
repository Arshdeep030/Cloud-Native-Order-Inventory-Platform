import logging
import time
import uuid
import httpx
from fastapi import FastAPI, Request, Response, Depends, HTTPException
from pydantic import BaseModel
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

try:
    from app.config import settings
    from app.logging_config import configure_logging
    from app.auth.security import (
        USERS,
        create_access_token,
        verify_password,
        get_current_user,
        require_role,
    )
except ImportError:
    from gateway.app.config import settings
    from gateway.app.logging_config import configure_logging
    from gateway.app.auth.security import (
        USERS,
        create_access_token,
        verify_password,
        get_current_user,
        require_role,
    )

configure_logging("gateway")
logger = logging.getLogger("gateway.http")

GATEWAY_HTTP_REQUESTS_TOTAL = Counter(
    "gateway_http_requests_total",
    "Total HTTP requests received by Gateway",
    ["method", "endpoint", "status"]
)

GATEWAY_HTTP_DURATION_SECONDS = Histogram(
    "gateway_http_request_duration_seconds",
    "Gateway HTTP request duration in seconds",
    ["method", "endpoint"]
)

app = FastAPI(
    title="Cloud Order Platform API Gateway"
)

ORDER_SERVICE_URL = settings.order_service_url


@app.middleware("http")
async def gateway_logging_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    correlation_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())

    request.state.request_id = request_id
    request.state.correlation_id = correlation_id

    start_time = time.perf_counter()
    response = await call_next(request)
    duration_s = time.perf_counter() - start_time
    duration_ms = round(duration_s * 1000, 2)

    GATEWAY_HTTP_REQUESTS_TOTAL.labels(
        method=request.method,
        endpoint=request.url.path,
        status=str(response.status_code)
    ).inc()

    GATEWAY_HTTP_DURATION_SECONDS.labels(
        method=request.method,
        endpoint=request.url.path
    ).observe(duration_s)

    logger.info(
        f"{request.method} {request.url.path} -> {response.status_code} in {duration_ms}ms",
        extra={
            "request_id": request_id,
            "correlation_id": correlation_id,
            "event": "gateway_request",
            "extra_data": {
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms
            }
        }
    )

    response.headers["X-Request-ID"] = request_id
    response.headers["X-Correlation-ID"] = correlation_id
    return response


class LoginRequest(BaseModel):
    username: str
    password: str


def get_forward_headers(request: Request, correlation_id: str) -> dict:
    headers = {
        "X-Correlation-ID": correlation_id,
    }
    for header_name in ["authorization", "idempotency-key", "x-request-id", "content-type"]:
        val = request.headers.get(header_name)
        if val:
            headers[header_name] = val
    return headers


@app.get("/")
def root():
    return {
        "message": "Cloud Order Platform API Gateway"
    }


@app.post("/auth/login")
def login(request: LoginRequest):
    user = USERS.get(request.username)

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials"
        )

    if not verify_password(request.password, user["password_hash"]):
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials"
        )

    token = create_access_token(
        user_id=user["id"],
        role=user["role"]
    )

    return {
        "access_token": token,
        "token_type": "bearer"
    }


@app.post("/orders")
@app.post("/orders/")
async def create_order(
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    correlation_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
    headers = get_forward_headers(request, correlation_id)
    body = await request.body()

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{ORDER_SERVICE_URL}/orders/",
            content=body,
            headers=headers
        )

    return Response(
        content=response.content,
        status_code=response.status_code,
        headers={
            "Content-Type": response.headers.get("content-type", "application/json"),
            "X-Correlation-ID": correlation_id
        }
    )


@app.get("/orders/{order_id}")
async def get_order(
    order_id: int,
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    correlation_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
    headers = get_forward_headers(request, correlation_id)

    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{ORDER_SERVICE_URL}/orders/{order_id}",
            headers=headers
        )

    return Response(
        content=response.content,
        status_code=response.status_code,
        headers={
            "Content-Type": response.headers.get("content-type", "application/json"),
            "X-Correlation-ID": correlation_id
        }
    )


@app.get("/orders")
@app.get("/orders/")
async def list_orders(
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    correlation_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
    headers = get_forward_headers(request, correlation_id)

    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{ORDER_SERVICE_URL}/orders/",
            headers=headers
        )

    return Response(
        content=response.content,
        status_code=response.status_code,
        headers={"Content-Type": response.headers.get("content-type", "application/json")}
    )


@app.post("/products")
@app.post("/products/")
async def create_product(request: Request):
    correlation_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
    headers = get_forward_headers(request, correlation_id)
    body = await request.body()

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{ORDER_SERVICE_URL}/products/",
            content=body,
            headers=headers
        )

    return Response(
        content=response.content,
        status_code=response.status_code,
        headers={"Content-Type": response.headers.get("content-type", "application/json")}
    )


@app.get("/products/{product_id}")
async def get_product(product_id: int, request: Request):
    correlation_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
    headers = get_forward_headers(request, correlation_id)

    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{ORDER_SERVICE_URL}/products/{product_id}",
            headers=headers
        )

    return Response(
        content=response.content,
        status_code=response.status_code,
        headers={"Content-Type": response.headers.get("content-type", "application/json")}
    )


@app.delete("/products/{product_id}")
async def delete_product(
    product_id: int,
    request: Request,
    current_user: dict = Depends(require_role("admin"))
):
    correlation_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
    headers = get_forward_headers(request, correlation_id)

    async with httpx.AsyncClient() as client:
        response = await client.delete(
            f"{ORDER_SERVICE_URL}/products/{product_id}",
            headers=headers
        )

    return Response(
        content=response.content,
        status_code=response.status_code,
        headers={"Content-Type": response.headers.get("content-type", "application/json")}
    )


@app.get("/health/live")
def liveness():
    return {"status": "alive"}


@app.get("/health/ready")
def readiness():
    return {"status": "ready"}


@app.get("/metrics")
def gateway_metrics():
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )
