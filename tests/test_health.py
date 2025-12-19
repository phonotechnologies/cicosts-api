"""Health endpoint tests."""


def test_health_endpoint(client):
    """Test health check returns ok."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "checks" in data


def test_root_endpoint(client):
    """Test root returns API info."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "CICosts API"
