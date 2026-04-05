
import pytest
from unittest.mock import patch, MagicMock
import json
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
    """GET /health doit retourner {"status": "ok"}."""
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


#tests POST /athletes
def test_create_athlete_success(client):
    """POST /athletes avec données valides doit retourner 201 + un id."""
    mock_db = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.lastrowid = 42  
    mock_db.cursor.return_value = mock_cursor

    payload = {"nom": "Alice", "email": "alice@test.com", "poids_kg": 65.0}

    with patch("main.get_db", return_value=mock_db):
        res = client.post(
            "/athletes",
            data=json.dumps(payload),
            content_type="application/json"
        )

    assert res.status_code == 201
    data = res.get_json()
    assert "id" in data
    assert data["id"] == 42    

def test_create_athlete_missing_nom(client):
    """POST /athletes sans nom doit retourner 400 avec le champ manquant."""
    payload = {"email": "alice@test.com"} 

    res = client.post(
        "/athletes",
        data=json.dumps(payload),
        content_type="application/json"
    )

    assert res.status_code == 400
    data = res.get_json()
    assert "missing" in data
    assert "nom" in data["missing"]


def test_create_athlete_missing_email(client):
    """POST /athletes sans email doit retourner 400."""
    payload = {"nom": "Bob"}  

    res = client.post(
        "/athletes",
        data=json.dumps(payload),
        content_type="application/json"
    )

    assert res.status_code == 400
    data = res.get_json()
    assert "email" in data["missing"]


def test_create_athlete_empty_body(client):
    """POST /athletes sans body doit retourner 400."""
    res = client.post(
        "/athletes",
        data="{}",
        content_type="application/json"
    )

    assert res.status_code == 400        


#test GET /seances
def test_get_seances_status_200(client):
    """GET /seances doit retourner HTTP 200."""
    mock_db = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = [
        {
            "id": 1,
            "athlete_id": 1,
            "titre": "Push Day",
            "date_seance": "2025-01-01",
            "duree_min": 75,
            "athlete_nom": "Khalil"
        }
    ]
    mock_db.cursor.return_value = mock_cursor

    with patch("main.get_db", return_value=mock_db):
        res = client.get("/seances")

    assert res.status_code == 200


def test_get_seances_returns_list(client):
    """GET /seances doit retourner un tableau JSON."""
    mock_db = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = []
    mock_db.cursor.return_value = mock_cursor

    with patch("main.get_db", return_value=mock_db):
        res = client.get("/seances")

    data = res.get_json()
    assert isinstance(data, list)    