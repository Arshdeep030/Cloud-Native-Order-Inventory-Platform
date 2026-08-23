
import pytest

from app.order_schema import OrderCreate


def register_and_login(client, email: str):
    registration = client.post(
        "/auth/register",
        json={"email": email, "password": "password123"}
    )
    assert registration.status_code == 201

    login = client.post(
        "/auth/login",
        json={"email": email, "password": "password123"}
    )
    assert login.status_code == 200

    return registration.json()["id"], {
        "Authorization": f"Bearer {login.json()['access_token']}"
    }


def order_headers(auth_headers: dict[str, str], key: str) -> dict[str, str]:
    return auth_headers | {"Idempotency-Key": key}


def test_valid_order():
    order = OrderCreate(
        items=[
            {
                "product_id": 1,
                "quantity": 2
            }
        ]
    )

    assert len(order.items) == 1


def test_order_requires_items():
    with pytest.raises(ValueError):
        OrderCreate(
            items=[]
        )


def test_order_quantity_must_be_positive():
    with pytest.raises(ValueError):
        OrderCreate(
            items=[
                {
                    "product_id": 1,
                    "quantity": 0
                }
            ]
        )
        
def test_create_order(client):
    user_id, headers = register_and_login(client, "order-create@example.com")

    # Create a product first
    product_response = client.post(
        "/products/",
        json={
            "name": "Test Laptop",
            "description": "Testing laptop",
            "price": 1000,
            "quantity": 10
        }
    )

    assert product_response.status_code == 201

    product = product_response.json()

    # Create order
    order_response = client.post(
        "/orders/",
        json={
            "items": [
                {
                    "product_id": product["id"],
                    "quantity": 2
                }
            ]
        },
        headers=order_headers(headers, "create-order-123")
    )

    assert order_response.status_code == 201

    order = order_response.json()

    assert order["customer_id"] == user_id
    assert order["status"] == "PENDING"
    assert order["total_amount"] == 2000

    assert len(order["items"]) == 1
    assert order["items"][0]["product_id"] == product["id"]
    assert order["items"][0]["quantity"] == 2
    assert order["items"][0]["unit_price"] == 1000

def test_order_reduces_inventory(client):
    _, headers = register_and_login(client, "order-inventory@example.com")

    product_response = client.post(
        "/products/",
        json={
            "name": "Test Phone",
            "description": "Testing phone",
            "price": 500,
            "quantity": 10
        }
    )

    assert product_response.status_code == 201

    product = product_response.json()

    product_id = product["id"]

    # Create order for 3
    order_response = client.post(
        "/orders/",
        json={
            "items": [
                {
                    "product_id": product_id,
                    "quantity": 3
                }
            ]
        },
        headers=order_headers(headers, "inventory-order-123")
    )

    assert order_response.status_code == 201

    # Check inventory
    product_response = client.get(
        f"/products/{product_id}"
    )

    assert product_response.status_code == 200

    product = product_response.json()

    assert product["quantity"] == 7

def test_order_insufficient_inventory(client):
    _, headers = register_and_login(client, "order-inventory-error@example.com")

    product_response = client.post(
        "/products/",
        json={
            "name": "Test Monitor",
            "description": "Testing monitor",
            "price": 300,
            "quantity": 5
        }
    )

    product = product_response.json()

    response = client.post(
        "/orders/",
        json={
            "items": [
                {
                    "product_id": product["id"],
                    "quantity": 10
                }
            ]
        },
        headers=order_headers(headers, "insufficient-inventory-123")
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INSUFFICIENT_INVENTORY"
    assert response.json()["error"]["message"] == (
        f"Insufficient inventory for product {product['id']}"
    )

    product_response = client.get(f"/products/{product['id']}")

    assert product_response.status_code == 200
    assert product_response.json()["quantity"] == 5


def test_order_combines_duplicate_product_quantities(client):
    _, headers = register_and_login(client, "order-duplicate-item@example.com")

    product_response = client.post(
        "/products/",
        json={
            "name": "Test Cable",
            "description": "Testing cable",
            "price": 10,
            "quantity": 3
        }
    )
    product = product_response.json()

    response = client.post(
        "/orders/",
        json={
            "items": [
                {"product_id": product["id"], "quantity": 2},
                {"product_id": product["id"], "quantity": 2}
            ]
        },
        headers=order_headers(headers, "duplicate-product-lines-123")
    )

    assert response.status_code == 409
    assert client.get(f"/products/{product['id']}").json()["quantity"] == 3
    
def test_order_missing_product(client):
    _, headers = register_and_login(client, "order-missing-product@example.com")

    response = client.post(
        "/orders/",
        json={
            "items": [
                {
                    "product_id": 999999,
                    "quantity": 1
                }
            ]
        },
        headers=order_headers(headers, "missing-product-123")
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "PRODUCT_NOT_FOUND"
    assert response.json()["error"]["message"] == "Product 999999 was not found"


def test_order_can_only_be_read_by_its_owner(client):
    owner_id, owner_headers = register_and_login(client, "order-owner@example.com")
    _, other_headers = register_and_login(client, "order-other@example.com")

    product_response = client.post(
        "/products/",
        json={
            "name": "Test Keyboard",
            "description": "Testing keyboard",
            "price": 100,
            "quantity": 2
        }
    )
    product_id = product_response.json()["id"]

    create_response = client.post(
        "/orders/",
        json={"items": [{"product_id": product_id, "quantity": 1}]},
        headers=order_headers(owner_headers, "owner-order-123")
    )
    assert create_response.status_code == 201
    assert create_response.json()["customer_id"] == owner_id

    order_id = create_response.json()["id"]

    assert client.get(f"/orders/{order_id}", headers=owner_headers).status_code == 200
    assert client.get(f"/orders/{order_id}", headers=other_headers).status_code == 403


def test_get_missing_order_returns_structured_error(client):
    _, headers = register_and_login(client, "missing-order@example.com")

    response = client.get("/orders/999999", headers=headers)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ORDER_NOT_FOUND"
    assert response.json()["error"]["message"] == "Order 999999 was not found"


def test_duplicate_order_is_idempotent(client):
    _, auth_headers = register_and_login(client, "idempotent-order@example.com")
    headers = order_headers(auth_headers, "duplicate-order-123")

    product_response = client.post(
        "/products/",
        json={
            "name": "Test Idempotent Laptop",
            "description": "Testing idempotency",
            "price": 1200,
            "quantity": 2
        }
    )
    product_id = product_response.json()["id"]
    payload = {"items": [{"product_id": product_id, "quantity": 1}]}

    response1 = client.post("/orders/", json=payload, headers=headers)
    response2 = client.post("/orders/", json=payload, headers=headers)

    assert response1.status_code == 201
    assert response2.status_code == 201
    assert response1.json()["id"] == response2.json()["id"]
    assert client.get(f"/products/{product_id}").json()["quantity"] == 1


def test_different_idempotency_keys_create_orders(client):
    _, auth_headers = register_and_login(client, "different-keys@example.com")

    product_response = client.post(
        "/products/",
        json={
            "name": "Test Idempotent Mouse",
            "description": "Testing separate keys",
            "price": 50,
            "quantity": 2
        }
    )
    product_id = product_response.json()["id"]
    payload = {"items": [{"product_id": product_id, "quantity": 1}]}

    response1 = client.post(
        "/orders/",
        json=payload,
        headers=order_headers(auth_headers, "order-key-a")
    )
    response2 = client.post(
        "/orders/",
        json=payload,
        headers=order_headers(auth_headers, "order-key-b")
    )

    assert response1.status_code == 201
    assert response2.status_code == 201
    assert response1.json()["id"] != response2.json()["id"]
    
