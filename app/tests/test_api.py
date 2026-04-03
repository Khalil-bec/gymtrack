
import pytest
from unittest.mock import patch, MagicMock
from main import app

@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client
#tests /health
def test_health_status_200(client):
    """GET /health doit retourner HTTP 200."""
    res = client.get("/health")
    assert res.status_code == 200
 
 
def test_health_json_content(client):
    """GET /health doit retourner {"status": "ok"}."""
    res = client.get("/health")
    data = res.get_json()
    assert data["status"] == "ok"        