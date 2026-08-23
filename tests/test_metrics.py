def test_metrics_endpoint(client):
    response = client.get("/metrics")

    assert response.status_code == 200
    assert "http_requests_total" in response.text
    assert "http_request_duration_seconds" in response.text
    assert "orders_created_total" in response.text
    assert "orders_failed_total" in response.text
    assert "products_created_total" in response.text


def test_metrics_incremented_on_request(client):
    # Perform a request
    client.get("/")

    response = client.get("/metrics")
    assert response.status_code == 200
    assert 'http_requests_total{endpoint="/",method="GET",status="200"}' in response.text


def test_product_creation_increments_metric(client):
    response = client.post(
        "/products/",
        json={
            "name": "Prometheus Test Product",
            "description": "Test description",
            "price": 49.99,
            "quantity": 10
        }
    )
    assert response.status_code == 201

    metrics_response = client.get("/metrics")
    assert metrics_response.status_code == 200
    assert "products_created_total" in metrics_response.text


def test_failed_order_increments_metric(client):
    # Register and login user
    reg = client.post(
        "/auth/register",
        json={"email": "metrics_fail_test@example.com", "password": "password123"}
    )
    login = client.post(
        "/auth/login",
        json={"email": "metrics_fail_test@example.com", "password": "password123"}
    )
    token = login.json()["access_token"]

    # Order for non-existent product fails with 404
    response = client.post(
        "/orders/",
        json={
            "items": [{"product_id": 999999, "quantity": 1}]
        },
        headers={
            "Authorization": f"Bearer {token}",
            "Idempotency-Key": "failed-order-test-1"
        }
    )
    assert response.status_code == 404

    metrics_response = client.get("/metrics")
    assert metrics_response.status_code == 200
    assert "orders_failed_total" in metrics_response.text
