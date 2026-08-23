from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
import httpx

from gateway.app.main import app
from gateway.app.auth.security import create_access_token


client = TestClient(app)


def test_gateway_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {
        "message": "Cloud Order Platform API Gateway"
    }


def test_gateway_health_checks():
    live = client.get("/health/live")
    assert live.status_code == 200
    assert live.json() == {"status": "alive"}

    ready = client.get("/health/ready")
    assert ready.status_code == 200
    assert ready.json() == {"status": "ready"}


def test_login_success():
    response = client.post(
        "/auth/login",
        json={
            "username": "arsh",
            "password": "password123"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_invalid_password():
    response = client.post(
        "/auth/login",
        json={
            "username": "arsh",
            "password": "wrongpassword"
        }
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid credentials"


def test_login_unknown_user():
    response = client.post(
        "/auth/login",
        json={
            "username": "nonexistent_user",
            "password": "password123"
        }
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid credentials"


def test_order_requires_authentication():
    response = client.get("/orders/1")
    assert response.status_code == 401


def test_order_with_invalid_token():
    response = client.get(
        "/orders/1",
        headers={"Authorization": "Bearer invalid-token-xyz"}
    )
    assert response.status_code == 401


@patch.object(httpx.AsyncClient, "get")
def test_order_with_valid_token_forwarding(mock_get):
    token = create_access_token(user_id=1, role="customer")

    mock_resp = AsyncMock()
    mock_resp.status_code = 200
    mock_resp.content = b'{"id": 1, "customer_id": 1, "status": "CONFIRMED", "total_amount": 100.0}'
    mock_resp.headers = {"content-type": "application/json"}
    mock_get.return_value = mock_resp

    response = client.get(
        "/orders/1",
        headers={"Authorization": f"Bearer {token}", "X-Correlation-ID": "test-corr-gw-1"}
    )

    assert response.status_code == 200
    assert response.json()["status"] == "CONFIRMED"
    assert response.headers["X-Correlation-ID"] == "test-corr-gw-1"


@patch.object(httpx.AsyncClient, "post")
def test_create_order_with_valid_token_forwarding(mock_post):
    token = create_access_token(user_id=1, role="customer")

    mock_resp = AsyncMock()
    mock_resp.status_code = 201
    mock_resp.content = b'{"id": 101, "customer_id": 1, "status": "PENDING", "total_amount": 200.0}'
    mock_resp.headers = {"content-type": "application/json"}
    mock_post.return_value = mock_resp

    response = client.post(
        "/orders",
        json={"items": [{"product_id": 1, "quantity": 2}]},
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "gw-key-1"}
    )

    assert response.status_code == 201
    data = response.json()
    assert data["id"] == 101
    assert "X-Correlation-ID" in response.headers


def test_admin_authorization_customer_rejected():
    customer_token = create_access_token(user_id=1, role="customer")

    response = client.delete(
        "/products/1",
        headers={"Authorization": f"Bearer {customer_token}"}
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient permissions"


@patch.object(httpx.AsyncClient, "delete")
def test_admin_authorization_admin_allowed(mock_delete):
    admin_token = create_access_token(user_id=2, role="admin")

    mock_resp = AsyncMock()
    mock_resp.status_code = 200
    mock_resp.content = b'{"message": "Product deleted successfully"}'
    mock_resp.headers = {"content-type": "application/json"}
    mock_delete.return_value = mock_resp

    response = client.delete(
        "/products/1",
        headers={"Authorization": f"Bearer {admin_token}"}
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Product deleted successfully"
