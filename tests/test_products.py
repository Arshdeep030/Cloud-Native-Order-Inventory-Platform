def test_root(client):
    response = client.get("/")

    assert response.status_code == 200

    assert response.json() == {
        "message": "Cloud Order Platform API"
    }


def test_create_product(client):
    response = client.post(
        "/products/",
        json={
            "name": "Laptop",
            "description": "Development laptop",
            "price": 1200,
            "quantity": 10
        }
    )

    assert response.status_code == 201

    data = response.json()

    assert data["name"] == "Laptop"
    assert data["price"] == 1200
    assert data["quantity"] == 10


def test_create_product_invalid_price(client):
    response = client.post(
        "/products/",
        json={
            "name": "Laptop",
            "description": "Development laptop",
            "price": -100,
            "quantity": 10
        }
    )

    assert response.status_code == 422


def test_get_missing_product(client):
    response = client.get("/products/999999")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "PRODUCT_NOT_FOUND"
    assert response.json()["error"]["message"] == "Product 999999 was not found"
