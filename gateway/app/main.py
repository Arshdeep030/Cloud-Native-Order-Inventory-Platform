import uuid
import httpx
from fastapi import FastAPI, Request, Response, Depends, HTTPException
from pydantic import BaseModel

try:
    from app.config import settings
    from app.auth.security import (
        USERS,
        create_access_token,
        verify_password,
        get_current_user,
        require_role,
    )
except ImportError:
    from gateway.app.config import settings
    from gateway.app.auth.security import (
        USERS,
        create_access_token,
        verify_password,
        get_current_user,
        require_role,
    )

app = FastAPI(
    title="Cloud Order Platform API Gateway"
)

ORDER_SERVICE_URL = settings.order_service_url


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
