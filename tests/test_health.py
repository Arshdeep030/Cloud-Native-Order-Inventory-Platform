def test_liveness(client):

    response = client.get(
        "/health/live"
    )

    assert response.status_code == 200

    assert response.json() == {
        "status": "alive"
    }


def test_readiness(client):

    response = client.get(
        "/health/ready"
    )

    assert response.status_code == 200

    assert response.json() == {
        "status": "ready"
    }
