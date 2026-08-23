def test_register_user(client):

    response = client.post(
        "/auth/register",
        json={
            "email": "test@example.com",
            "password": "password123"
        }
    )

    assert response.status_code == 201

    data = response.json()

    assert data["email"] == "test@example.com"
    assert data["role"] == "customer"

    assert "password" not in data
    assert "password_hash" not in data
    
def test_login_user(client):

    client.post(
        "/auth/register",
        json={
            "email": "login@example.com",
            "password": "password123"
        }
    )

    response = client.post(
        "/auth/login",
        json={
            "email": "login@example.com",
            "password": "password123"
        }
    )

    assert response.status_code == 200

    data = response.json()

    assert "access_token" in data
    assert data["token_type"] == "bearer"
    
def test_invalid_login(client):

    client.post(
        "/auth/register",
        json={
            "email": "invalid@example.com",
            "password": "password123"
        }
    )

    response = client.post(
        "/auth/login",
        json={
            "email": "invalid@example.com",
            "password": "wrongpassword"
        }
    )

    assert response.status_code == 401
    
def test_duplicate_registration(client):

    user = {
        "email": "duplicate@example.com",
        "password": "password123"
    }

    first_response = client.post(
        "/auth/register",
        json=user
    )

    assert first_response.status_code == 201

    second_response = client.post(
        "/auth/register",
        json=user
    )

    assert second_response.status_code == 409


def test_protected_endpoint_without_token(client):
    response = client.get("/orders/1")

    assert response.status_code == 401


def test_invalid_token(client):
    response = client.get(
        "/orders/1",
        headers={"Authorization": "Bearer invalid-token"}
    )

    assert response.status_code == 401
