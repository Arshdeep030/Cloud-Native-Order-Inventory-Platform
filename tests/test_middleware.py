def test_request_id_is_returned(client):

    response = client.get("/")

    assert response.status_code == 200
    assert "X-Request-ID" in response.headers
    assert response.headers["X-Request-ID"]


def test_request_id_is_preserved(client):

    response = client.get(
        "/",
        headers={
            "X-Request-ID": "test-request-123"
        }
    )

    assert response.status_code == 200

    assert response.headers["X-Request-ID"] == (
        "test-request-123"
    )
