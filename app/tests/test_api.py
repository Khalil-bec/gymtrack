
import pytest
from unittest.mock import patch, MagicMock
# On importe l'objet app depuis main.py
# pour pouvoir créer un client de test
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
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

#test GET /athletes

def test_get_athletes(client):
    mock_db = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = [
        {"id": 1, "nom": "Khalil", "email": "k@test.com", "poids_kg": 80.5}
    ]
    mock_db.cursor.return_value = mock_cursor
 
    with patch("main.get_db", return_value=mock_db):
        res = client.get("/athletes")

    assert res.status_code == 200
    data = res.get_json()
    assert isinstance(data, list)
    assert data[0]["nom"] == "Khalil"    