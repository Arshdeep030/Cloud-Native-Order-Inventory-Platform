from app.repositories.cache_repository import cache_repository


def register_and_login(client, email: str):
    client.post(
        "/auth/register",
        json={"email": email, "password": "password123"}
    )
    login = client.post(
        "/auth/login",
        json={"email": email, "password": "password123"}
    )
    return {
        "Authorization": f"Bearer {login.json()['access_token']}"
    }


def test_cache_miss_stores_in_redis(client):
    product_res = client.post(
        "/products/",
        json={
            "name": "Cache Test Item",
            "description": "Testing cache miss",
            "price": 200,
            "quantity": 5
        }
    )
    product_id = product_res.json()["id"]

    assert cache_repository.get(f"product:{product_id}") is None

    get_res = client.get(f"/products/{product_id}")
    assert get_res.status_code == 200
    assert get_res.json()["name"] == "Cache Test Item"

    cached_data = cache_repository.get(f"product:{product_id}")
    assert cached_data is not None
    assert cached_data["id"] == product_id
    assert cached_data["name"] == "Cache Test Item"
    assert cached_data["price"] == 200


def test_cache_hit_returns_cached_data(client):
    product_res = client.post(
        "/products/",
        json={
            "name": "Original DB Item",
            "description": "Before cache injection",
            "price": 500,
            "quantity": 10
        }
    )
    product_id = product_res.json()["id"]

    cache_repository.set(
        f"product:{product_id}",
        {
            "id": product_id,
            "name": "Injected Cached Name",
            "description": "Cached Description",
            "price": 999.0,
            "quantity": 99
        }
    )

    get_res = client.get(f"/products/{product_id}")
    assert get_res.status_code == 200
    assert get_res.json()["name"] == "Injected Cached Name"
    assert get_res.json()["price"] == 999.0
    assert get_res.json()["quantity"] == 99


def test_cache_invalidation_on_update(client):
    product_res = client.post(
        "/products/",
        json={
            "name": "Update Cache Item",
            "description": "Testing cache invalidation on update",
            "price": 100,
            "quantity": 4
        }
    )
    product_id = product_res.json()["id"]

    client.get(f"/products/{product_id}")
    assert cache_repository.get(f"product:{product_id}") is not None

    update_res = client.put(
        f"/products/{product_id}",
        json={"price": 150}
    )
    assert update_res.status_code == 200

    assert cache_repository.get(f"product:{product_id}") is None

    get_res = client.get(f"/products/{product_id}")
    assert get_res.status_code == 200
    assert get_res.json()["price"] == 150
    assert cache_repository.get(f"product:{product_id}")["price"] == 150


def test_cache_invalidation_on_delete(client):
    product_res = client.post(
        "/products/",
        json={
            "name": "Delete Cache Item",
            "description": "Testing cache invalidation on delete",
            "price": 75,
            "quantity": 2
        }
    )
    product_id = product_res.json()["id"]

    client.get(f"/products/{product_id}")
    assert cache_repository.get(f"product:{product_id}") is not None

    del_res = client.delete(f"/products/{product_id}")
    assert del_res.status_code == 200

    assert cache_repository.get(f"product:{product_id}") is None


def test_cache_invalidation_on_order_creation(client):
    headers = register_and_login(client, "cache-order@example.com")

    product_res = client.post(
        "/products/",
        json={
            "name": "Order Cache Item",
            "description": "Testing cache invalidation on order",
            "price": 300,
            "quantity": 10
        }
    )
    product_id = product_res.json()["id"]

    client.get(f"/products/{product_id}")
    assert cache_repository.get(f"product:{product_id}")["quantity"] == 10

    order_res = client.post(
        "/orders/",
        json={"items": [{"product_id": product_id, "quantity": 3}]},
        headers=headers | {"Idempotency-Key": "cache-order-key-1"}
    )
    assert order_res.status_code == 201

    assert cache_repository.get(f"product:{product_id}") is None

    get_res = client.get(f"/products/{product_id}")
    assert get_res.status_code == 200
    assert get_res.json()["quantity"] == 7
