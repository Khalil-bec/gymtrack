
import pytest
from unittest.mock import patch, MagicMock
import json
import datetime
# On importe l'objet app depuis main.py
# pour pouvoir créer un client de test
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from main import app
import mysql.connector

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


def test_get_athletes_resume_seances(client):
    """GET /athletes doit donner, par client, la date de dernière séance (ISO) et le nombre de séances sur 4 semaines."""
    mock_db = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = [
        {"id": 1, "nom": "Khalil", "email": None, "poids_kg": None,
         "derniere_seance": datetime.date(2026, 3, 22), "seances_4_semaines": 6},
        {"id": 2, "nom": "Sarah", "email": "s@test.com", "poids_kg": None,
         "derniere_seance": None, "seances_4_semaines": 0},
    ]
    mock_db.cursor.return_value = mock_cursor

    with patch("main.get_db", return_value=mock_db):
        res = client.get("/athletes")

    data = res.get_json()
    assert data[0]["derniere_seance"] == "2026-03-22"
    assert data[0]["seances_4_semaines"] == 6
    assert data[1]["derniere_seance"] is None
    assert data[1]["seances_4_semaines"] == 0


def test_get_athletes_erreur_db(client):
    """GET /athletes doit renvoyer une 500 db_error en JSON et fermer la connexion si la requête échoue."""
    mock_db = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.execute.side_effect = mysql.connector.ProgrammingError(msg="Erreur SQL")
    mock_db.cursor.return_value = mock_cursor

    with patch("main.get_db", return_value=mock_db):
        res = client.get("/athletes")

    assert res.status_code == 500
    assert res.get_json()["error"] == "db_error"
    mock_db.close.assert_called_once()


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


def test_create_athlete_sans_email(client):
    """POST /athletes avec seulement un nom doit créer le client, email enregistré à NULL."""
    mock_db = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.lastrowid = 7
    mock_db.cursor.return_value = mock_cursor

    with patch("main.get_db", return_value=mock_db):
        res = client.post(
            "/athletes",
            data=json.dumps({"nom": "Bob"}),
            content_type="application/json"
        )

    assert res.status_code == 201
    assert res.get_json()["id"] == 7
    params = mock_cursor.execute.call_args[0][1]
    assert params[0] == "Bob"
    assert params[1] is None


def test_create_athlete_email_blanc(client):
    """POST /athletes avec un email fait d'espaces doit l'enregistrer à NULL, comme sans email."""
    mock_db = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.lastrowid = 8
    mock_db.cursor.return_value = mock_cursor

    with patch("main.get_db", return_value=mock_db):
        res = client.post(
            "/athletes",
            data=json.dumps({"nom": "Bob", "email": "   "}),
            content_type="application/json"
        )

    assert res.status_code == 201
    assert mock_cursor.execute.call_args[0][1][1] is None


def test_create_athlete_email_duplique(client):
    """POST /athletes avec un email déjà utilisé doit retourner 409."""
    mock_db = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.execute.side_effect = mysql.connector.IntegrityError(msg="Duplicate entry", errno=1062)
    mock_db.cursor.return_value = mock_cursor

    with patch("main.get_db", return_value=mock_db):
        res = client.post(
            "/athletes",
            data=json.dumps({"nom": "Alice", "email": "alice@test.com"}),
            content_type="application/json"
        )

    assert res.status_code == 409
    assert res.get_json()["error"] == "email_already_exists"


def test_create_athlete_autre_contrainte(client):
    """Une violation de contrainte autre qu'un doublon (ex. email NOT NULL sur un ancien schéma) doit être une 500, pas une 409."""
    mock_db = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.execute.side_effect = mysql.connector.IntegrityError(msg="Column 'email' cannot be null", errno=1048)
    mock_db.cursor.return_value = mock_cursor

    with patch("main.get_db", return_value=mock_db):
        res = client.post(
            "/athletes",
            data=json.dumps({"nom": "Bob"}),
            content_type="application/json"
        )

    assert res.status_code == 500
    assert res.get_json()["error"] == "db_error"


def test_create_athlete_erreur_db(client):
    """POST /athletes : une erreur MySQL qui n'est pas une contrainte doit donner une 500 db_error en JSON."""
    mock_db = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.execute.side_effect = mysql.connector.OperationalError(msg="Lost connection")
    mock_db.cursor.return_value = mock_cursor

    with patch("main.get_db", return_value=mock_db):
        res = client.post(
            "/athletes",
            data=json.dumps({"nom": "Bob"}),
            content_type="application/json"
        )

    assert res.status_code == 500
    assert res.get_json()["error"] == "db_error"
    mock_db.close.assert_called_once()


def test_create_athlete_email_invalide(client):
    """POST /athletes avec un email sans @ ni domaine doit retourner 400 invalid_field."""
    res = client.post(
        "/athletes",
        data=json.dumps({"nom": "Bob", "email": "bob@"}),
        content_type="application/json"
    )

    assert res.status_code == 400
    assert res.get_json() == {"error": "invalid_field", "field": "email"}


@pytest.mark.parametrize("payload, champ", [
    ({"nom": 123}, "nom"),
    ({"nom": "Bob", "email": 42}, "email"),
])
def test_create_athlete_champ_pas_texte(client, payload, champ):
    """POST /athletes avec un nom ou un email qui n'est pas du texte doit retourner 400 invalid_field."""
    res = client.post(
        "/athletes",
        data=json.dumps(payload),
        content_type="application/json"
    )

    assert res.status_code == 400
    assert res.get_json() == {"error": "invalid_field", "field": champ}


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