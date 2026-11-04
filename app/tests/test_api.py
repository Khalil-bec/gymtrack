
import pytest
from unittest.mock import patch, MagicMock
import json
import datetime
from decimal import Decimal
# On importe l'objet app depuis main.py
# pour pouvoir créer un client de test
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from main import app, resume_poids
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
    mock_cursor.fetchall.side_effect = [
        [{"id": 1, "nom": "Khalil", "email": "k@test.com", "aujourdhui": datetime.date(2026, 10, 30)}],
        [],
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
    mock_cursor.fetchall.side_effect = [
        [{"id": 1, "nom": "Khalil", "email": None, "aujourdhui": datetime.date(2026, 10, 30),
          "derniere_seance": datetime.date(2026, 3, 22), "seances_4_semaines": 6},
         {"id": 2, "nom": "Sarah", "email": "s@test.com", "aujourdhui": datetime.date(2026, 10, 30),
          "derniere_seance": None, "seances_4_semaines": 0}],
        [],
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

# tests resume_poids (poids actuel + évolution sur 4 semaines)
def p(jour, poids):
    return {"date_pesee": datetime.date(2026, 10, jour) if isinstance(jour, int) else jour, "poids_kg": Decimal(poids)}


def test_resume_poids_evolution_depuis_la_pesee_d_il_y_a_4_semaines():
    """Évolution = dernière pesée − la plus récente pesée datée au plus tard aujourd'hui − 28 jours."""
    pesees = [
        p(datetime.date(2026, 9, 25), "83.0"),
        p(datetime.date(2026, 10, 1), "82.4"),   # la plus récente avant le 02/10 (30/10 − 28 j)
        p(15, "81.0"),
        p(29, "80.5"),
    ]
    assert resume_poids(pesees, datetime.date(2026, 10, 30)) == {"poids_actuel": 80.5, "evolution_4_semaines": -1.9}


def test_resume_poids_sans_pesee():
    """Aucune pesée : poids et évolution vides (affichés « — »)."""
    assert resume_poids([], datetime.date(2026, 10, 30)) == {"poids_actuel": None, "evolution_4_semaines": None}


def test_resume_poids_sans_pesee_assez_ancienne():
    """Que des pesées de moins de 4 semaines : poids connu, évolution vide."""
    pesees = [p(10, "70.0"), p(29, "71.2")]
    assert resume_poids(pesees, datetime.date(2026, 10, 30)) == {"poids_actuel": 71.2, "evolution_4_semaines": None}


def test_resume_poids_ignore_les_pesees_futures():
    """Une pesée datée après aujourd'hui ne compte pas encore, comme les séances futures."""
    pesees = [p(datetime.date(2026, 9, 1), "90.0"), p(20, "88.0"), p(datetime.date(2026, 11, 15), "85.0")]
    assert resume_poids(pesees, datetime.date(2026, 10, 30)) == {"poids_actuel": 88.0, "evolution_4_semaines": -2.0}


# tests poids de départ (POST /athletes)
def test_create_athlete_avec_poids_de_depart_cree_une_pesee(client):
    """Un poids de départ crée le client sans poids, puis exactement une pesée datée d'aujourd'hui."""
    mock_db = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.lastrowid = 7
    mock_db.cursor.return_value = mock_cursor

    with patch("main.get_db", return_value=mock_db):
        res = client.post(
            "/athletes",
            data=json.dumps({"nom": "Bob", "poids_kg": 82.5}),
            content_type="application/json"
        )

    assert res.status_code == 201
    requetes = [c[0] for c in mock_cursor.execute.call_args_list]
    assert len(requetes) == 2
    assert "poids_kg" not in requetes[0][0]
    assert "INSERT INTO pesees" in requetes[1][0]
    assert "CURDATE()" in requetes[1][0]
    assert requetes[1][1] == (7, 82.5)
    mock_db.commit.assert_called_once()


def test_create_athlete_sans_poids_ne_cree_pas_de_pesee(client):
    """Sans poids de départ, aucune pesée n'est créée."""
    mock_db = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.lastrowid = 7
    mock_db.cursor.return_value = mock_cursor

    with patch("main.get_db", return_value=mock_db):
        res = client.post(
            "/athletes",
            data=json.dumps({"nom": "Bob", "poids_kg": None}),
            content_type="application/json"
        )

    assert res.status_code == 201
    assert mock_cursor.execute.call_count == 1
    assert "pesees" not in mock_cursor.execute.call_args[0][0]


@pytest.mark.parametrize("poids", [True, "nan", "inf", "abc", 0, -5, 1000])
def test_create_athlete_poids_invalide(client, poids):
    """Un poids de départ qui n'est pas un nombre entre 0 (exclu) et 1000 (exclu) doit retourner 400 invalid_field."""
    res = client.post(
        "/athletes",
        data=json.dumps({"nom": "Bob", "poids_kg": poids}),
        content_type="application/json"
    )

    assert res.status_code == 400
    assert res.get_json() == {"error": "invalid_field", "field": "poids_kg"}


# tests GET /athletes/<id> (profil)
def test_get_athlete_inconnu_404(client):
    """GET /athletes/<id> pour un id qui n'existe pas doit retourner 404 athlete_not_found."""
    mock_db = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = None
    mock_db.cursor.return_value = mock_cursor

    with patch("main.get_db", return_value=mock_db):
        res = client.get("/athletes/999")

    assert res.status_code == 404
    assert res.get_json() == {"error": "athlete_not_found"}
    mock_db.close.assert_called_once()


def test_get_athlete_profil(client):
    """GET /athletes/<id> renvoie les infos du client, le résumé des séances et le poids actuel + évolution."""
    mock_db = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = {
        "id": 1, "nom": "Khalil", "email": "k@test.com",
        "created_at": datetime.datetime(2026, 2, 3, 10, 0), "aujourdhui": datetime.date(2026, 10, 30),
        "derniere_seance": datetime.date(2026, 10, 28), "seances_4_semaines": 6,
    }
    mock_cursor.fetchall.return_value = [p(datetime.date(2026, 9, 30), "82.4"), p(29, "80.5")]
    mock_db.cursor.return_value = mock_cursor

    with patch("main.get_db", return_value=mock_db):
        res = client.get("/athletes/1")

    assert res.status_code == 200
    assert res.get_json() == {
        "id": 1, "nom": "Khalil", "email": "k@test.com", "created_at": "2026-02-03T10:00:00",
        "derniere_seance": "2026-10-28", "seances_4_semaines": 6,
        "poids_actuel": 80.5, "evolution_4_semaines": -1.9,
    }


# tests GET /athletes : poids et évolution dans la liste
def test_get_athletes_poids_et_evolution(client):
    """GET /athletes donne pour chaque client son poids actuel et l'évolution sur 4 semaines (None sans pesée)."""
    mock_db = MagicMock()
    mock_cursor = MagicMock()
    aujourdhui = datetime.date(2026, 10, 30)
    mock_cursor.fetchall.side_effect = [
        [{"id": 1, "nom": "Khalil", "email": None, "aujourdhui": aujourdhui, "derniere_seance": None, "seances_4_semaines": 0},
         {"id": 2, "nom": "Sarah", "email": None, "aujourdhui": aujourdhui, "derniere_seance": None, "seances_4_semaines": 0}],
        [{"athlete_id": 1, **p(datetime.date(2026, 9, 30), "82.4")}, {"athlete_id": 1, **p(29, "80.5")}],
    ]
    mock_db.cursor.return_value = mock_cursor

    with patch("main.get_db", return_value=mock_db):
        res = client.get("/athletes")

    data = res.get_json()
    assert "aujourdhui" not in data[0]
    assert (data[0]["poids_actuel"], data[0]["evolution_4_semaines"]) == (80.5, -1.9)
    assert (data[1]["poids_actuel"], data[1]["evolution_4_semaines"]) == (None, None)


# tests GET /athletes/<id>/pesees
def test_get_pesees_athlete_inconnu_404(client):
    """GET /athletes/<id>/pesees pour un client qui n'existe pas doit retourner 404 athlete_not_found."""
    mock_db = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = None
    mock_db.cursor.return_value = mock_cursor

    with patch("main.get_db", return_value=mock_db):
        res = client.get("/athletes/999/pesees")

    assert res.status_code == 404
    assert res.get_json() == {"error": "athlete_not_found"}


def test_get_pesees(client):
    """GET /athletes/<id>/pesees renvoie les pesées avec la date en ISO et le poids en nombre (pour le graphique)."""
    mock_db = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = {"id": 1}
    mock_cursor.fetchall.return_value = [
        {"id": 3, **p(1, "82.40")},
        {"id": 5, **p(29, "80.50")},
    ]
    mock_db.cursor.return_value = mock_cursor

    with patch("main.get_db", return_value=mock_db):
        res = client.get("/athletes/1/pesees")

    assert res.status_code == 200
    assert res.get_json() == [
        {"id": 3, "date_pesee": "2026-10-01", "poids_kg": 82.4},
        {"id": 5, "date_pesee": "2026-10-29", "poids_kg": 80.5},
    ]


# tests POST /athletes/<id>/pesees
def poster_pesee(client, payload, mock_db=None):
    with patch("main.get_db", return_value=mock_db or MagicMock()):
        return client.post("/athletes/1/pesees", data=json.dumps(payload), content_type="application/json")


def test_create_pesee_success(client):
    """POST /athletes/<id>/pesees avec date + poids valides doit retourner 201 + l'id de la pesée."""
    mock_db = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.lastrowid = 12
    mock_db.cursor.return_value = mock_cursor

    res = poster_pesee(client, {"date_pesee": "2026-10-29", "poids_kg": "80.5"}, mock_db)

    assert res.status_code == 201
    assert res.get_json() == {"id": 12}
    assert mock_cursor.execute.call_args[0][1] == (1, "2026-10-29", 80.5)
    mock_db.commit.assert_called_once()


def test_create_pesee_champs_manquants(client):
    """POST /athletes/<id>/pesees sans date ni poids doit retourner 400 avec les deux champs manquants."""
    res = poster_pesee(client, {})

    assert res.status_code == 400
    assert res.get_json() == {"error": "missing_fields", "missing": ["date_pesee", "poids_kg"]}


@pytest.mark.parametrize("date", ["2026-02-30", "30/10/2026", "hier", 20261029])
def test_create_pesee_date_invalide(client, date):
    """Une date qui n'est pas une vraie date AAAA-MM-JJ doit retourner 400 invalid_field date_pesee."""
    res = poster_pesee(client, {"date_pesee": date, "poids_kg": 80})

    assert res.status_code == 400
    assert res.get_json() == {"error": "invalid_field", "field": "date_pesee"}


@pytest.mark.parametrize("poids", ["abc", 0, 1000, True])
def test_create_pesee_poids_invalide(client, poids):
    """Un poids hors de ]0 ; 1000[ ou qui n'est pas un nombre doit retourner 400 invalid_field poids_kg."""
    res = poster_pesee(client, {"date_pesee": "2026-10-29", "poids_kg": poids})

    assert res.status_code == 400
    assert res.get_json() == {"error": "invalid_field", "field": "poids_kg"}


def test_create_pesee_athlete_inconnu_404(client):
    """Une pesée pour un client qui n'existe pas (clé étrangère refusée, 1452) doit retourner 404."""
    mock_db = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.execute.side_effect = mysql.connector.IntegrityError(msg="foreign key constraint fails", errno=1452)
    mock_db.cursor.return_value = mock_cursor

    res = poster_pesee(client, {"date_pesee": "2026-10-29", "poids_kg": 80}, mock_db)

    assert res.status_code == 404
    assert res.get_json() == {"error": "athlete_not_found"}


# tests DELETE /pesees/<id>
def test_delete_pesee(client):
    """DELETE /pesees/<id> supprime la pesée et retourne 204 sans contenu."""
    mock_db = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.rowcount = 1
    mock_db.cursor.return_value = mock_cursor

    with patch("main.get_db", return_value=mock_db):
        res = client.delete("/pesees/5")

    assert res.status_code == 204
    assert mock_cursor.execute.call_args[0][1] == (5,)
    mock_db.commit.assert_called_once()


def test_delete_pesee_inconnue_404(client):
    """DELETE /pesees/<id> pour une pesée qui n'existe pas (aucune ligne supprimée) doit retourner 404."""
    mock_db = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.rowcount = 0
    mock_db.cursor.return_value = mock_cursor

    with patch("main.get_db", return_value=mock_db):
        res = client.delete("/pesees/999")

    assert res.status_code == 404
    assert res.get_json() == {"error": "pesee_not_found"}


# corrections après revue
def test_resume_poids_meme_jour_prend_la_derniere_saisie():
    """Deux pesées le même jour : le poids actuel est la dernière saisie (id le plus grand), comme sur le graphique."""
    pesees = [{"id": 9, **p(29, "80.2")}, {"id": 4, **p(29, "81.0")}]
    assert resume_poids(pesees, datetime.date(2026, 10, 30))["poids_actuel"] == 80.2


def test_resume_poids_toutes_anciennes_pas_d_evolution():
    """Si la dernière pesée a elle-même plus de 4 semaines, il n'y a pas d'évolution à montrer (pas « 0 kg »)."""
    pesees = [p(datetime.date(2026, 8, 1), "75.0")]
    assert resume_poids(pesees, datetime.date(2026, 10, 30)) == {"poids_actuel": 75.0, "evolution_4_semaines": None}


@pytest.mark.parametrize("poids", [999.999, 0.001])
def test_create_pesee_poids_arrondi_hors_limites(client, poids):
    """Un poids qui, arrondi au centième comme en base, vaut 1000 ou 0 doit retourner 400 (pas une 500 MySQL)."""
    res = poster_pesee(client, {"date_pesee": "2026-10-29", "poids_kg": poids})

    assert res.status_code == 400
    assert res.get_json() == {"error": "invalid_field", "field": "poids_kg"}


@pytest.mark.parametrize("url", ["/athletes", "/athletes/1/pesees"])
def test_post_corps_json_qui_n_est_pas_un_objet(client, url):
    """Un corps JSON qui n'est pas un objet (liste, texte) est traité comme vide : 400 missing_fields, pas une 500."""
    res = client.post(url, data=json.dumps([1]), content_type="application/json")

    assert res.status_code == 400
    assert res.get_json()["error"] == "missing_fields"


def test_create_pesee_date_future(client):
    """Une pesée datée de plus d'un jour dans le futur doit retourner 400 invalid_field date_pesee."""
    future = (datetime.date.today() + datetime.timedelta(days=2)).isoformat()
    res = poster_pesee(client, {"date_pesee": future, "poids_kg": 80})

    assert res.status_code == 400
    assert res.get_json() == {"error": "invalid_field", "field": "date_pesee"}


# tests PUT /athletes/<id>
def modifier_athlete(client, athlete_id, payload, rowcount=1):
    """Envoie un PUT /athletes/<id> avec un get_db mocké ; rowcount = lignes trouvées par l'UPDATE (0 = client inconnu)."""
    mock_db = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.rowcount = rowcount
    mock_db.cursor.return_value = mock_cursor
    with patch("main.get_db", return_value=mock_db):
        res = client.put(
            f"/athletes/{athlete_id}",
            data=json.dumps(payload),
            content_type="application/json"
        )
    return res, mock_db, mock_cursor


def test_update_athlete_success(client):
    """PUT /athletes/<id> met à jour le nom et l'email (nettoyés comme à la création) et renvoie le client modifié."""
    res, mock_db, mock_cursor = modifier_athlete(client, 3, {"nom": " Paulo Dybala ", "email": "Paulo@GymTrack.com"})

    assert res.status_code == 200
    assert res.get_json() == {"id": 3, "nom": "Paulo Dybala", "email": "paulo@gymtrack.com"}
    assert mock_cursor.execute.call_args[0][1] == ("Paulo Dybala", "paulo@gymtrack.com", 3)
    mock_db.commit.assert_called_once()


def test_update_athlete_inconnu_404(client):
    """PUT /athletes/<id> pour un client qui n'existe pas (aucune ligne trouvée) doit retourner 404, sans valider."""
    res, mock_db, _ = modifier_athlete(client, 999, {"nom": "Personne"}, rowcount=0)

    assert res.status_code == 404
    assert res.get_json() == {"error": "athlete_not_found"}
    mock_db.commit.assert_not_called()


@pytest.mark.parametrize("payload", [{"email": "a@test.com"}, {"nom": "   ", "email": "a@test.com"}])
def test_update_athlete_nom_manquant(client, payload):
    """PUT /athletes/<id> sans nom (absent ou que des espaces) doit retourner 400 missing_fields nom."""
    res, mock_db, _ = modifier_athlete(client, 3, payload)

    assert res.status_code == 400
    assert res.get_json() == {"error": "missing_fields", "missing": ["nom"]}
    mock_db.cursor.assert_not_called()


@pytest.mark.parametrize("payload, champ", [
    ({"nom": "Paulo", "email": "pas-un-email"}, "email"),
    ({"nom": 5}, "nom"),
    ({"nom": "Paulo", "email": ["a@test.com"]}, "email"),
    ({"nom": "x" * 101}, "nom"),
    ({"nom": "Paulo", "email": "a" * 140 + "@gymtrack.com"}, "email"),
])
def test_update_athlete_champ_invalide(client, payload, champ):
    """PUT /athletes/<id> : email mal formé, champ qui n'est pas du texte ou trop long pour sa colonne → 400 invalid_field."""
    res, mock_db, _ = modifier_athlete(client, 3, payload)

    assert res.status_code == 400
    assert res.get_json() == {"error": "invalid_field", "field": champ}
    mock_db.cursor.assert_not_called()


def test_update_athlete_email_deja_utilise_409(client):
    """PUT /athletes/<id> avec l'email d'un autre client doit retourner 409 email_already_exists."""
    mock_db = MagicMock()
    mock_db.cursor.return_value.execute.side_effect = mysql.connector.IntegrityError(msg="Duplicate entry", errno=1062)

    with patch("main.get_db", return_value=mock_db):
        res = client.put("/athletes/3", data=json.dumps({"nom": "Paulo", "email": "messi@gymtrack.com"}),
                         content_type="application/json")

    assert res.status_code == 409
    assert res.get_json() == {"error": "email_already_exists"}
    mock_db.commit.assert_not_called()


@pytest.mark.parametrize("payload", [{"nom": "Paulo", "email": ""}, {"nom": "Paulo", "email": None}, {"nom": "Paulo"}])
def test_update_athlete_email_efface(client, payload):
    """PUT /athletes/<id> avec un email vide ou absent l'efface : il est enregistré à NULL."""
    res, _, mock_cursor = modifier_athlete(client, 3, payload)

    assert res.status_code == 200
    assert res.get_json()["email"] is None
    assert mock_cursor.execute.call_args[0][1] == ("Paulo", None, 3)


def test_update_athlete_erreur_db(client):
    """PUT /athletes/<id> : une erreur MySQL doit donner une 500 db_error en JSON."""
    mock_db = MagicMock()
    mock_db.cursor.return_value.execute.side_effect = mysql.connector.Error(msg="Lost connection")

    with patch("main.get_db", return_value=mock_db):
        res = client.put("/athletes/3", data=json.dumps({"nom": "Paulo"}), content_type="application/json")

    assert res.status_code == 500
    assert res.get_json()["error"] == "db_error"
    mock_db.close.assert_called_once()


@pytest.mark.parametrize("payload", [{"nom": "x" * 101}, {"nom": "Bob", "email": "a" * 140 + "@gymtrack.com"}])
def test_create_athlete_champ_trop_long(client, payload):
    """POST /athletes : un nom ou un email plus long que sa colonne → 400 invalid_field, pas une 500 MySQL."""
    res = client.post("/athletes", data=json.dumps(payload), content_type="application/json")

    assert res.status_code == 400
    assert res.get_json()["error"] == "invalid_field"


# tests GET /exercices
def test_get_exercices(client):
    """GET /exercices renvoie la liste (nom, type, nombre de séances qui l'utilisent), triée par nom côté SQL."""
    mock_db = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = [
        {"id": 1, "nom": "Développé couché", "type": "charge", "nb_seances": 0},
        {"id": 14, "nom": "Tractions", "type": "poids_du_corps", "nb_seances": 0},
    ]
    mock_db.cursor.return_value = mock_cursor

    with patch("main.get_db", return_value=mock_db):
        res = client.get("/exercices")

    assert res.status_code == 200
    assert res.get_json() == [
        {"id": 1, "nom": "Développé couché", "type": "charge", "nb_seances": 0},
        {"id": 14, "nom": "Tractions", "type": "poids_du_corps", "nb_seances": 0},
    ]
    assert "ORDER BY nom" in mock_cursor.execute.call_args[0][0]
    mock_db.close.assert_called_once()


# tests POST /exercices
def poster_exercice(client, payload, mock_db=None):
    """Envoie un POST /exercices avec un get_db mocké (nouvel id = 19 par défaut)."""
    if mock_db is None:
        mock_db = MagicMock()
        mock_db.cursor.return_value.lastrowid = 19
    with patch("main.get_db", return_value=mock_db):
        return client.post("/exercices", data=json.dumps(payload), content_type="application/json")


def test_create_exercice_success(client):
    """POST /exercices ajoute un exercice (nom nettoyé) et renvoie 201 avec l'exercice créé."""
    mock_db = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.lastrowid = 19
    mock_db.cursor.return_value = mock_cursor

    res = poster_exercice(client, {"nom": "  Gainage lesté ", "type": "charge"}, mock_db)

    assert res.status_code == 201
    assert res.get_json() == {"id": 19, "nom": "Gainage lesté", "type": "charge", "nb_seances": 0}
    assert mock_cursor.execute.call_args[0][1] == ("Gainage lesté", "charge")
    mock_db.commit.assert_called_once()


@pytest.mark.parametrize("payload, missing", [
    ({}, ["nom", "type"]),
    ({"nom": "   ", "type": "charge"}, ["nom"]),
    ({"nom": "Gainage"}, ["type"]),
    ({"nom": "Gainage", "type": ""}, ["type"]),
])
def test_create_exercice_champs_manquants(client, payload, missing):
    """POST /exercices sans nom ou sans type doit retourner 400 missing_fields avec les champs manquants."""
    res = poster_exercice(client, payload)

    assert res.status_code == 400
    assert res.get_json() == {"error": "missing_fields", "missing": missing}


@pytest.mark.parametrize("payload, champ", [
    ({"nom": "Gainage", "type": "cardio"}, "type"),
    ({"nom": "Gainage", "type": ["charge"]}, "type"),
    ({"nom": "Gainage", "type": 0}, "type"),
    ({"nom": "Gainage", "type": False}, "type"),
    ({"nom": 5, "type": "charge"}, "nom"),
    ({"nom": "x" * 101, "type": "charge"}, "nom"),
])
def test_create_exercice_champ_invalide(client, payload, champ):
    """POST /exercices : type inconnu, nom qui n'est pas du texte ou trop long → 400 invalid_field, sans toucher la base."""
    mock_db = MagicMock()

    res = poster_exercice(client, payload, mock_db)

    assert res.status_code == 400
    assert res.get_json() == {"error": "invalid_field", "field": champ}
    mock_db.cursor.assert_not_called()


def test_create_exercice_doublon_409(client):
    """POST /exercices avec un nom déjà pris (la collation ignore casse et accents) doit retourner 409 exercice_already_exists."""
    mock_db = MagicMock()
    mock_db.cursor.return_value.execute.side_effect = mysql.connector.IntegrityError(msg="Duplicate entry", errno=1062)

    res = poster_exercice(client, {"nom": "developpe couche", "type": "charge"}, mock_db)

    assert res.status_code == 409
    assert res.get_json() == {"error": "exercice_already_exists"}
    mock_db.commit.assert_not_called()


@pytest.mark.parametrize("url, methode", [("/exercices", "get"), ("/exercices", "post")])
def test_exercices_erreur_db(client, url, methode):
    """GET et POST /exercices : une erreur MySQL doit donner une 500 db_error en JSON et fermer la connexion."""
    mock_db = MagicMock()
    mock_db.cursor.return_value.execute.side_effect = mysql.connector.Error(msg="Lost connection")

    with patch("main.get_db", return_value=mock_db):
        res = getattr(client, methode)(url, data=json.dumps({"nom": "Gainage", "type": "charge"}),
                                       content_type="application/json")

    assert res.status_code == 500
    assert res.get_json()["error"] == "db_error"
    mock_db.close.assert_called_once()


def test_create_exercice_espaces_interieurs_reduits(client):
    """POST /exercices : les espaces répétés dans le nom sont réduits à un seul, pour que la contrainte UNIQUE
    voie « Développé  couché » comme un doublon de « Développé couché »."""
    mock_db = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.lastrowid = 19
    mock_db.cursor.return_value = mock_cursor

    res = poster_exercice(client, {"nom": "Développé \t  couché", "type": "charge"}, mock_db)

    assert res.status_code == 201
    assert mock_cursor.execute.call_args[0][1] == ("Développé couché", "charge")


def test_create_exercice_autre_contrainte_500(client):
    """POST /exercices : une violation de contrainte autre qu'un doublon est une vraie erreur (500), pas une 409."""
    mock_db = MagicMock()
    mock_db.cursor.return_value.execute.side_effect = mysql.connector.IntegrityError(msg="Column 'type' cannot be null", errno=1048)

    res = poster_exercice(client, {"nom": "Gainage", "type": "charge"}, mock_db)

    assert res.status_code == 500
    assert res.get_json()["error"] == "db_error"


# tests GET /athletes/<id>/seances
def test_get_seances_athlete(client):
    """GET /athletes/<id>/seances renvoie les séances de ce client seulement, la plus récente d'abord, avec le nombre d'exercices."""
    mock_db = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = {"id": 1}
    mock_cursor.fetchall.return_value = [
        {"id": 2, "titre": "Push", "date_seance": datetime.date(2026, 10, 28), "duree_min": 75, "nb_exercices": 2},
        {"id": 1, "titre": "Pull", "date_seance": datetime.date(2026, 10, 25), "duree_min": None, "nb_exercices": 0},
    ]
    mock_db.cursor.return_value = mock_cursor

    with patch("main.get_db", return_value=mock_db):
        res = client.get("/athletes/1/seances")

    assert res.status_code == 200
    assert res.get_json() == [
        {"id": 2, "titre": "Push", "date_seance": "2026-10-28", "duree_min": 75, "nb_exercices": 2},
        {"id": 1, "titre": "Pull", "date_seance": "2026-10-25", "duree_min": None, "nb_exercices": 0},
    ]
    requete, params = mock_cursor.execute.call_args[0]
    assert "WHERE s.athlete_id = %s" in requete and "ORDER BY s.date_seance DESC" in requete
    assert params == (1,)


def test_get_seances_athlete_inconnu_404(client):
    """GET /athletes/<id>/seances pour un client qui n'existe pas doit retourner 404 athlete_not_found."""
    mock_db = MagicMock()
    mock_db.cursor.return_value.fetchone.return_value = None

    with patch("main.get_db", return_value=mock_db):
        res = client.get("/athletes/999/seances")

    assert res.status_code == 404
    assert res.get_json() == {"error": "athlete_not_found"}


# tests POST /athletes/<id>/seances
def poster_seance(client, athlete_id, payload, mock_db=None):
    """Envoie un POST /athletes/<id>/seances avec un get_db mocké (nouvel id = 42 par défaut)."""
    if mock_db is None:
        mock_db = MagicMock()
        mock_db.cursor.return_value.lastrowid = 42
    with patch("main.get_db", return_value=mock_db):
        return client.post(f"/athletes/{athlete_id}/seances", data=json.dumps(payload), content_type="application/json")


def test_create_seance_success(client):
    """POST /athletes/<id>/seances crée la séance pour ce client (pris dans l'URL) et renvoie 201 avec son id."""
    mock_db = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.lastrowid = 42
    mock_db.cursor.return_value = mock_cursor

    res = poster_seance(client, 3, {"titre": "  Push  ", "date_seance": "2026-10-28", "duree_min": 75}, mock_db)

    assert res.status_code == 201
    assert res.get_json() == {"id": 42}
    assert mock_cursor.execute.call_args[0][1] == (3, "Push", "2026-10-28", 75)
    mock_db.commit.assert_called_once()


@pytest.mark.parametrize("duree", [None, ""])
def test_create_seance_sans_duree(client, duree):
    """La durée est facultative : absente ou vide, elle est enregistrée à NULL."""
    mock_db = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.lastrowid = 42
    mock_db.cursor.return_value = mock_cursor

    res = poster_seance(client, 3, {"titre": "Push", "date_seance": "2026-10-28", "duree_min": duree}, mock_db)

    assert res.status_code == 201
    assert mock_cursor.execute.call_args[0][1][3] is None


@pytest.mark.parametrize("payload, missing", [
    ({}, ["titre", "date_seance"]),
    ({"titre": "   ", "date_seance": "2026-10-28"}, ["titre"]),
    ({"titre": "Push", "date_seance": ""}, ["date_seance"]),
])
def test_create_seance_champs_manquants(client, payload, missing):
    """POST /athletes/<id>/seances sans titre ou sans date doit retourner 400 missing_fields."""
    res = poster_seance(client, 3, payload)

    assert res.status_code == 400
    assert res.get_json() == {"error": "missing_fields", "missing": missing}


DANS_3_JOURS = (datetime.date.today() + datetime.timedelta(days=3)).isoformat()


@pytest.mark.parametrize("payload, champ", [
    ({"titre": 5, "date_seance": "2026-10-28"}, "titre"),
    ({"titre": "x" * 201, "date_seance": "2026-10-28"}, "titre"),
    ({"titre": "Push", "date_seance": "2026-02-30"}, "date_seance"),
    ({"titre": "Push", "date_seance": DANS_3_JOURS}, "date_seance"),
    ({"titre": "Push", "date_seance": "2026-10-28", "duree_min": 0}, "duree_min"),
    ({"titre": "Push", "date_seance": "2026-10-28", "duree_min": -30}, "duree_min"),
    ({"titre": "Push", "date_seance": "2026-10-28", "duree_min": 601}, "duree_min"),
    ({"titre": "Push", "date_seance": "2026-10-28", "duree_min": 75.5}, "duree_min"),
    ({"titre": "Push", "date_seance": "2026-10-28", "duree_min": True}, "duree_min"),
    ({"titre": "Push", "date_seance": "2026-10-28", "duree_min": "une heure"}, "duree_min"),
    # « ² » passe str.isdigit() mais int() le refuse : doit rester une 400, pas une 500
    ({"titre": "Push", "date_seance": "2026-10-28", "duree_min": "²"}, "duree_min"),
])
def test_create_seance_champ_invalide(client, payload, champ):
    """POST /athletes/<id>/seances : titre pas texte ou trop long, date invalide ou à venir, durée hors 1–600 min → 400 invalid_field."""
    mock_db = MagicMock()

    res = poster_seance(client, 3, payload, mock_db)

    assert res.status_code == 400
    assert res.get_json() == {"error": "invalid_field", "field": champ}
    mock_db.cursor.assert_not_called()


def test_create_seance_duree_en_texte(client):
    """Une durée envoyée en texte par le formulaire ("75") est acceptée et enregistrée en nombre."""
    mock_db = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.lastrowid = 42
    mock_db.cursor.return_value = mock_cursor

    res = poster_seance(client, 3, {"titre": "Push", "date_seance": "2026-10-28", "duree_min": "75"}, mock_db)

    assert res.status_code == 201
    assert mock_cursor.execute.call_args[0][1][3] == 75


def test_create_seance_athlete_inconnu_404(client):
    """POST /athletes/<id>/seances pour un client qui n'existe pas (clé étrangère refusée) doit retourner 404."""
    mock_db = MagicMock()
    mock_db.cursor.return_value.execute.side_effect = mysql.connector.IntegrityError(msg="FK", errno=1452)

    res = poster_seance(client, 999, {"titre": "Push", "date_seance": "2026-10-28"}, mock_db)

    assert res.status_code == 404
    assert res.get_json() == {"error": "athlete_not_found"}


# tests GET /seances/<id>
def test_get_seance(client):
    """GET /seances/<id> renvoie l'en-tête (titre, date ISO, durée, client) et les exercices dans l'ordre d'ajout,
    chacun avec son type et ses séries dans l'ordre ; un exercice sans série a une liste vide."""
    mock_db = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = {
        "id": 42, "titre": "Push", "date_seance": datetime.date(2026, 10, 28), "duree_min": None,
        "athlete_id": 3, "athlete_nom": "Paulo Dybala",
    }
    # Une ligne par série (LEFT JOIN) ; serie_id vide = exercice encore sans série
    mock_cursor.fetchall.return_value = [
        {"log_id": 7, "exercice_id": 1, "nom": "Développé couché", "type": "charge", "ordre": 1,
         "serie_id": 20, "numero_serie": 1, "poids_kg": Decimal("80.00"), "repetitions": 8, "repos_sec": 120},
        {"log_id": 7, "exercice_id": 1, "nom": "Développé couché", "type": "charge", "ordre": 1,
         "serie_id": 21, "numero_serie": 2, "poids_kg": Decimal("77.50"), "repetitions": 8, "repos_sec": 120},
        {"log_id": 8, "exercice_id": 15, "nom": "Dips", "type": "poids_du_corps", "ordre": 2,
         "serie_id": 22, "numero_serie": 1, "poids_kg": None, "repetitions": 12, "repos_sec": 90},
        {"log_id": 9, "exercice_id": 5, "nom": "Squat", "type": "charge", "ordre": 3,
         "serie_id": None, "numero_serie": None, "poids_kg": None, "repetitions": None, "repos_sec": None},
    ]
    mock_db.cursor.return_value = mock_cursor

    with patch("main.get_db", return_value=mock_db):
        res = client.get("/seances/42")

    assert res.status_code == 200
    assert res.get_json() == {
        "id": 42, "titre": "Push", "date_seance": "2026-10-28", "duree_min": None,
        "athlete_id": 3, "athlete_nom": "Paulo Dybala",
        "exercices": [
            {"id": 7, "exercice_id": 1, "nom": "Développé couché", "type": "charge", "series": [
                {"id": 20, "numero_serie": 1, "poids_kg": 80.0, "repetitions": 8, "repos_sec": 120},
                {"id": 21, "numero_serie": 2, "poids_kg": 77.5, "repetitions": 8, "repos_sec": 120},
            ]},
            {"id": 8, "exercice_id": 15, "nom": "Dips", "type": "poids_du_corps", "series": [
                {"id": 22, "numero_serie": 1, "poids_kg": None, "repetitions": 12, "repos_sec": 90},
            ]},
            {"id": 9, "exercice_id": 5, "nom": "Squat", "type": "charge", "series": []},
        ],
    }
    requete, params = mock_cursor.execute.call_args[0]
    # l.id départage deux exercices de même ordre : l'ordre affiché reste stable d'un chargement à l'autre
    assert "ORDER BY l.ordre, l.id, s.numero_serie" in requete and params == (42,)


def test_get_seance_inconnue_404(client):
    """GET /seances/<id> pour une séance qui n'existe pas doit retourner 404 seance_not_found."""
    mock_db = MagicMock()
    mock_db.cursor.return_value.fetchone.return_value = None

    with patch("main.get_db", return_value=mock_db):
        res = client.get("/seances/999")

    assert res.status_code == 404
    assert res.get_json() == {"error": "seance_not_found"}


# tests PUT /seances/<id>
def modifier_seance(client, seance_id, payload, rowcount=1):
    """Envoie un PUT /seances/<id> avec un get_db mocké ; rowcount = lignes trouvées par l'UPDATE (0 = séance inconnue)."""
    mock_db = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.rowcount = rowcount
    mock_db.cursor.return_value = mock_cursor
    with patch("main.get_db", return_value=mock_db):
        res = client.put(f"/seances/{seance_id}", data=json.dumps(payload), content_type="application/json")
    return res, mock_db, mock_cursor


def test_update_seance_success(client):
    """PUT /seances/<id> remplace titre, date et durée (ajoutée après coup) et renvoie la séance modifiée."""
    res, mock_db, mock_cursor = modifier_seance(client, 42, {"titre": "Push lourd", "date_seance": "2026-10-27", "duree_min": "80"})

    assert res.status_code == 200
    assert res.get_json() == {"id": 42, "titre": "Push lourd", "date_seance": "2026-10-27", "duree_min": 80}
    assert mock_cursor.execute.call_args[0][1] == ("Push lourd", "2026-10-27", 80, 42)
    mock_db.commit.assert_called_once()


def test_update_seance_inconnue_404(client):
    """PUT /seances/<id> pour une séance qui n'existe pas (aucune ligne trouvée) doit retourner 404, sans valider."""
    res, mock_db, _ = modifier_seance(client, 999, {"titre": "Push", "date_seance": "2026-10-27"}, rowcount=0)

    assert res.status_code == 404
    assert res.get_json() == {"error": "seance_not_found"}
    mock_db.commit.assert_not_called()


@pytest.mark.parametrize("payload, attendu", [
    ({"date_seance": "2026-10-27"}, {"error": "missing_fields", "missing": ["titre"]}),
    ({"titre": "Push", "date_seance": "2026-10-27", "duree_min": 0}, {"error": "invalid_field", "field": "duree_min"}),
])
def test_update_seance_validation(client, payload, attendu):
    """PUT /seances/<id> valide comme la création (même fonction) : 400 sans toucher la base."""
    res, mock_db, _ = modifier_seance(client, 42, payload)

    assert res.status_code == 400
    assert res.get_json() == attendu
    mock_db.cursor.assert_not_called()


# tests DELETE /seances/<id>
def test_delete_seance(client):
    """DELETE /seances/<id> supprime la séance (ses exercices et séries partent en cascade) et retourne 204."""
    mock_db = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.rowcount = 1
    mock_db.cursor.return_value = mock_cursor

    with patch("main.get_db", return_value=mock_db):
        res = client.delete("/seances/42")

    assert res.status_code == 204
    assert mock_cursor.execute.call_args[0][1] == (42,)
    mock_db.commit.assert_called_once()


def test_delete_seance_inconnue_404(client):
    """DELETE /seances/<id> pour une séance qui n'existe pas doit retourner 404 seance_not_found."""
    mock_db = MagicMock()
    mock_db.cursor.return_value.rowcount = 0

    with patch("main.get_db", return_value=mock_db):
        res = client.delete("/seances/999")

    assert res.status_code == 404
    assert res.get_json() == {"error": "seance_not_found"}


@pytest.mark.parametrize("methode, url", [
    ("get", "/athletes/1/seances"), ("post", "/athletes/1/seances"),
    ("get", "/seances/42"), ("put", "/seances/42"), ("delete", "/seances/42"),
])
def test_seances_erreur_db(client, methode, url):
    """Routes des séances : une erreur MySQL doit donner une 500 db_error en JSON et fermer la connexion."""
    mock_db = MagicMock()
    mock_db.cursor.return_value.execute.side_effect = mysql.connector.Error(msg="Lost connection")

    with patch("main.get_db", return_value=mock_db):
        res = getattr(client, methode)(url, data=json.dumps({"titre": "Push", "date_seance": "2026-10-28"}),
                                       content_type="application/json")

    assert res.status_code == 500
    assert res.get_json()["error"] == "db_error"
    mock_db.close.assert_called_once()


# tests ticket 06 : saisie des séances
def test_get_exercices_compte_les_seances_reelles(client):
    """GET /exercices compte les séances qui utilisent chaque exercice (via exercice_logs) ; LEFT JOIN pour
    qu'un exercice jamais utilisé reste dans la liste avec 0."""
    mock_db = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = [{"id": 1, "nom": "Développé couché", "type": "charge", "nb_seances": 3}]
    mock_db.cursor.return_value = mock_cursor

    with patch("main.get_db", return_value=mock_db):
        res = client.get("/exercices")

    assert res.get_json()[0]["nb_seances"] == 3
    requete = mock_cursor.execute.call_args[0][0]
    assert "LEFT JOIN exercice_logs" in requete and "COUNT(DISTINCT" in requete


# tests POST /seances/<id>/exercices
def ajouter_exercice(client, seance_id, payload, mock_db=None):
    """Envoie un POST /seances/<id>/exercices avec un get_db mocké ; par défaut la séance existe (nouvel id = 9)."""
    if mock_db is None:
        mock_db = MagicMock()
        mock_db.cursor.return_value.fetchone.return_value = {"id": seance_id}
        mock_db.cursor.return_value.lastrowid = 9
    with patch("main.get_db", return_value=mock_db):
        return client.post(f"/seances/{seance_id}/exercices", data=json.dumps(payload), content_type="application/json")


def test_ajouter_exercice_a_la_seance(client):
    """POST /seances/<id>/exercices ajoute un exercice de la liste à la fin de la séance et renvoie 201 avec son id."""
    mock_db = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = {"id": 42}
    mock_cursor.lastrowid = 9
    mock_db.cursor.return_value = mock_cursor

    res = ajouter_exercice(client, 42, {"exercice_id": 5}, mock_db)

    assert res.status_code == 201
    assert res.get_json() == {"id": 9}
    verification = mock_cursor.execute.call_args_list[0][0][0]
    requete, params = mock_cursor.execute.call_args[0]
    # La séance est verrouillée le temps de l'ajout : deux ajouts simultanés ne prennent pas le même ordre
    assert "FOR UPDATE" in verification
    # Ordre = dernier ordre de la séance + 1 (1 pour le premier exercice)
    assert "MAX(ordre)" in requete and params == (42, 5, 42)
    mock_db.commit.assert_called_once()


@pytest.mark.parametrize("payload, attendu", [
    ({}, {"error": "missing_fields", "missing": ["exercice_id"]}),
    ({"exercice_id": "Squat"}, {"error": "invalid_field", "field": "exercice_id"}),
    ({"exercice_id": True}, {"error": "invalid_field", "field": "exercice_id"}),
    ({"exercice_id": 0}, {"error": "invalid_field", "field": "exercice_id"}),
])
def test_ajouter_exercice_validation(client, payload, attendu):
    """POST /seances/<id>/exercices : exercice_id manquant ou qui n'est pas un id → 400, sans toucher la base."""
    mock_db = MagicMock()

    res = ajouter_exercice(client, 42, payload, mock_db)

    assert res.status_code == 400
    assert res.get_json() == attendu
    mock_db.cursor.assert_not_called()


def test_ajouter_exercice_seance_inconnue_404(client):
    """POST /seances/<id>/exercices pour une séance qui n'existe pas doit retourner 404 seance_not_found."""
    mock_db = MagicMock()
    mock_db.cursor.return_value.fetchone.return_value = None

    res = ajouter_exercice(client, 999, {"exercice_id": 5}, mock_db)

    assert res.status_code == 404
    assert res.get_json() == {"error": "seance_not_found"}


@pytest.mark.parametrize("errno, statut, attendu", [
    (1452, 400, {"error": "invalid_field", "field": "exercice_id"}),   # exercice absent de la liste
    (1062, 409, {"error": "exercice_deja_dans_seance"}),               # déjà dans cette séance
])
def test_ajouter_exercice_contraintes(client, errno, statut, attendu):
    """La séance existe, mais l'exercice n'est pas dans la liste (clé étrangère) ou y est déjà (UNIQUE)."""
    mock_db = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = {"id": 42}
    mock_cursor.execute.side_effect = [None, mysql.connector.IntegrityError(msg="contrainte", errno=errno)]
    mock_db.cursor.return_value = mock_cursor

    res = ajouter_exercice(client, 42, {"exercice_id": 5}, mock_db)

    assert res.status_code == statut
    assert res.get_json() == attendu
    mock_db.commit.assert_not_called()


# tests POST /exercice-logs/<id>/series
def ajouter_serie(client, log_id, payload, type_exercice="charge", numero=1):
    """Envoie un POST /exercice-logs/<id>/series ; la base mockée dit le type de l'exercice (None = exercice noté inconnu)
    puis le prochain numéro de série."""
    mock_db = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchone.side_effect = [
        None if type_exercice is None else {"type": type_exercice},
        {"suivant": numero},
    ]
    mock_cursor.lastrowid = 30
    mock_db.cursor.return_value = mock_cursor
    with patch("main.get_db", return_value=mock_db):
        res = client.post(f"/exercice-logs/{log_id}/series", data=json.dumps(payload), content_type="application/json")
    return res, mock_db, mock_cursor


def test_ajouter_serie_avec_charge(client):
    """Une série d'un exercice avec charge est enregistrée tout de suite, numérotée à la suite, et renvoyée en 201."""
    res, mock_db, mock_cursor = ajouter_serie(client, 7, {"poids_kg": "77.5", "repetitions": "8", "repos_sec": "120"}, numero=3)

    assert res.status_code == 201
    assert res.get_json() == {"id": 30, "numero_serie": 3, "poids_kg": 77.5, "repetitions": 8, "repos_sec": 120}
    requetes = [c[0][0] for c in mock_cursor.execute.call_args_list]
    # L'exercice noté est verrouillé le temps de l'ajout : deux séries simultanées ne prennent pas le même numéro
    assert "FOR UPDATE" in requetes[0]
    # Numéro = dernier numéro de cet exercice noté + 1
    assert "MAX(numero_serie)" in requetes[1]
    insertion = [c for c in mock_cursor.execute.call_args_list if "INSERT INTO series" in c[0][0]][0]
    assert insertion[0][1] == (7, 3, 77.5, 8, 120)
    mock_db.commit.assert_called_once()


@pytest.mark.parametrize("poids", [None, ""])
def test_ajouter_serie_poids_du_corps(client, poids):
    """Au poids du corps, la série n'a pas de poids (NULL) ; le repos vaut 90 s s'il n'est pas donné."""
    payload = {"repetitions": 12}
    if poids is not None:
        payload["poids_kg"] = poids
    res, _, mock_cursor = ajouter_serie(client, 8, payload, type_exercice="poids_du_corps")

    assert res.status_code == 201
    assert res.get_json() == {"id": 30, "numero_serie": 1, "poids_kg": None, "repetitions": 12, "repos_sec": 90}
    insertion = [c for c in mock_cursor.execute.call_args_list if "INSERT INTO series" in c[0][0]][0]
    assert insertion[0][1] == (8, 1, None, 12, 90)


@pytest.mark.parametrize("type_exercice, payload, attendu", [
    ("charge", {"poids_kg": 80}, {"error": "missing_fields", "missing": ["repetitions"]}),
    ("charge", {"repetitions": 8}, {"error": "missing_fields", "missing": ["poids_kg"]}),
    ("charge", {"poids_kg": 0, "repetitions": 8}, {"error": "invalid_field", "field": "poids_kg"}),
    ("charge", {"poids_kg": 1000, "repetitions": 8}, {"error": "invalid_field", "field": "poids_kg"}),
    ("poids_du_corps", {"poids_kg": 10, "repetitions": 8}, {"error": "invalid_field", "field": "poids_kg"}),
    ("charge", {"poids_kg": 80, "repetitions": 0}, {"error": "invalid_field", "field": "repetitions"}),
    ("charge", {"poids_kg": 80, "repetitions": 8.5}, {"error": "invalid_field", "field": "repetitions"}),
    ("charge", {"poids_kg": 80, "repetitions": 1000}, {"error": "invalid_field", "field": "repetitions"}),
    ("charge", {"poids_kg": 80, "repetitions": 8, "repos_sec": -1}, {"error": "invalid_field", "field": "repos_sec"}),
    ("charge", {"poids_kg": 80, "repetitions": 8, "repos_sec": 3601}, {"error": "invalid_field", "field": "repos_sec"}),
    # Plus de 4300 chiffres : int() lève ValueError en Python 3.11+ ; doit rester une 400 JSON
    ("charge", {"poids_kg": 80, "repetitions": "9" * 5000}, {"error": "invalid_field", "field": "repetitions"}),
])
def test_ajouter_serie_validation(client, type_exercice, payload, attendu):
    """Reps obligatoires (1–999), repos 0–3600 s ; poids obligatoire avec charge (0–1000 kg exclus), interdit au poids du corps."""
    res, mock_db, _ = ajouter_serie(client, 7, payload, type_exercice=type_exercice)

    assert res.status_code == 400
    assert res.get_json() == attendu
    mock_db.commit.assert_not_called()


def test_ajouter_serie_exercice_note_inconnu_404(client):
    """POST /exercice-logs/<id>/series pour un exercice noté qui n'existe pas doit retourner 404."""
    res, mock_db, _ = ajouter_serie(client, 999, {"poids_kg": 80, "repetitions": 8}, type_exercice=None)

    assert res.status_code == 404
    assert res.get_json() == {"error": "exercice_log_not_found"}
    mock_db.commit.assert_not_called()


@pytest.mark.parametrize("methode, url, payload", [
    ("post", "/seances/42/exercices", {"exercice_id": 5}),
    ("post", "/exercice-logs/7/series", {"poids_kg": 80, "repetitions": 8}),
])
def test_saisie_erreur_db(client, methode, url, payload):
    """Routes de saisie : une erreur MySQL doit donner une 500 db_error en JSON et fermer la connexion."""
    mock_db = MagicMock()
    mock_db.cursor.return_value.execute.side_effect = mysql.connector.Error(msg="Lost connection")

    with patch("main.get_db", return_value=mock_db):
        res = getattr(client, methode)(url, data=json.dumps(payload), content_type="application/json")

    assert res.status_code == 500
    assert res.get_json()["error"] == "db_error"
    mock_db.close.assert_called_once()


# tests ticket 07 : corriger les séries
def base_serie(serie):
    """Base mockée pour PUT/DELETE /series/<id>, dans l'ordre des lectures de verrouiller_serie :
    exercice noté de la série, exercice noté verrouillé (type), série relue verrouillée. serie=None : série inconnue."""
    mock_db = MagicMock()
    mock_cursor = MagicMock()
    if serie is None:
        mock_cursor.fetchone.side_effect = [None]
    else:
        mock_cursor.fetchone.side_effect = [
            {"exercice_log_id": 7},
            {"type": serie["type"]},
            {"numero_serie": serie["numero_serie"], "repos_sec": serie["repos_sec"]},
        ]
    mock_db.cursor.return_value = mock_cursor
    return mock_db, mock_cursor


SERIE_CHARGE = {"type": "charge", "numero_serie": 2, "repos_sec": 120}


def modifier_serie(client, serie_id, payload, serie=SERIE_CHARGE):
    """Envoie un PUT /series/<id> avec la base mockée de base_serie."""
    mock_db, mock_cursor = base_serie(serie)
    with patch("main.get_db", return_value=mock_db):
        res = client.put(f"/series/{serie_id}", data=json.dumps(payload), content_type="application/json")
    return res, mock_db, mock_cursor


def test_verrouillage_dans_le_meme_ordre_que_l_ajout(client):
    """PUT et DELETE /series/<id> verrouillent d'abord l'exercice noté, puis la série, comme l'ajout d'une série
    (qui verrouille l'exercice noté) : le même ordre partout évite les interblocages entre requêtes simultanées."""
    _, _, mock_cursor = modifier_serie(client, 21, {"poids_kg": 80, "repetitions": 6})

    requetes = [c[0][0] for c in mock_cursor.execute.call_args_list]
    assert "FROM exercice_logs" in requetes[1] and "FOR UPDATE OF l" in requetes[1]
    assert "FROM series" in requetes[2] and "FOR UPDATE" in requetes[2]


def test_modifier_serie(client):
    """PUT /series/<id> corrige poids, reps et repos (mêmes règles qu'à l'ajout) et renvoie la série corrigée."""
    res, mock_db, mock_cursor = modifier_serie(client, 21, {"poids_kg": "80", "repetitions": "6", "repos_sec": "150"})

    assert res.status_code == 200
    assert res.get_json() == {"id": 21, "numero_serie": 2, "poids_kg": 80.0, "repetitions": 6, "repos_sec": 150}
    requete, params = mock_cursor.execute.call_args[0]
    assert requete.startswith("UPDATE series") and params == (80.0, 6, 150, 21)
    mock_db.commit.assert_called_once()


@pytest.mark.parametrize("serie, payload, attendu", [
    (SERIE_CHARGE, {"repetitions": 6}, {"error": "missing_fields", "missing": ["poids_kg"]}),
    ({**SERIE_CHARGE, "type": "poids_du_corps"}, {"poids_kg": 10, "repetitions": 6}, {"error": "invalid_field", "field": "poids_kg"}),
    (SERIE_CHARGE, {"poids_kg": 80, "repetitions": 0}, {"error": "invalid_field", "field": "repetitions"}),
    (SERIE_CHARGE, {"poids_kg": 80, "repetitions": 6, "repos_sec": 4000}, {"error": "invalid_field", "field": "repos_sec"}),
])
def test_modifier_serie_validation(client, serie, payload, attendu):
    """PUT /series/<id> valide comme l'ajout : poids obligatoire avec charge, interdit au poids du corps."""
    res, mock_db, _ = modifier_serie(client, 21, payload, serie=serie)

    assert res.status_code == 400
    assert res.get_json() == attendu
    mock_db.commit.assert_not_called()


@pytest.mark.parametrize("repos", [None, ""])
def test_modifier_serie_repos_vide_garde_l_ancien(client, repos):
    """Corriger une série sans donner de repos garde le repos enregistré (120 s), au lieu de le remettre à 90 s ;
    au poids du corps, la série corrigée reste sans poids."""
    payload = {"repetitions": 15}
    if repos is not None:
        payload["repos_sec"] = repos
    res, _, mock_cursor = modifier_serie(client, 22, payload, serie={**SERIE_CHARGE, "type": "poids_du_corps"})

    assert res.status_code == 200
    assert res.get_json()["repos_sec"] == 120
    assert mock_cursor.execute.call_args[0][1] == (None, 15, 120, 22)


def test_modifier_serie_inconnue_404(client):
    """PUT /series/<id> pour une série qui n'existe pas doit retourner 404 serie_not_found, sans rien écrire."""
    res, mock_db, mock_cursor = modifier_serie(client, 999, {"poids_kg": 80, "repetitions": 6}, serie=None)

    assert res.status_code == 404
    assert res.get_json() == {"error": "serie_not_found"}
    assert not any(c[0][0].lstrip().startswith(("UPDATE", "DELETE")) for c in mock_cursor.execute.call_args_list)
    mock_db.commit.assert_not_called()


def test_modifier_serie_supprimee_entre_temps_404(client):
    """Série supprimée par une autre requête pendant qu'on attendait le verrou : 404, pas un faux « corrigée »."""
    mock_db, mock_cursor = base_serie(SERIE_CHARGE)
    mock_cursor.fetchone.side_effect = [{"exercice_log_id": 7}, {"type": "charge"}, None]

    with patch("main.get_db", return_value=mock_db):
        res = client.put("/series/21", data=json.dumps({"poids_kg": 80, "repetitions": 6}), content_type="application/json")

    assert res.status_code == 404
    mock_db.commit.assert_not_called()


def supprimer_serie(client, serie_id, serie=SERIE_CHARGE):
    """Envoie un DELETE /series/<id> avec la base mockée de base_serie."""
    mock_db, mock_cursor = base_serie(serie)
    with patch("main.get_db", return_value=mock_db):
        res = client.delete(f"/series/{serie_id}")
    return res, mock_db, mock_cursor


def test_supprimer_serie_renumerote(client):
    """DELETE /series/<id> supprime la série et décale les suivantes du même exercice (3 → 2, 4 → 3…), dans la même
    transaction ; 204 sans contenu."""
    res, mock_db, mock_cursor = supprimer_serie(client, 21)

    assert res.status_code == 204
    requetes = [(c[0][0], c[0][1]) for c in mock_cursor.execute.call_args_list]
    assert requetes[3] == ("DELETE FROM series WHERE id = %s", (21,))
    renumerotation, params = requetes[4]
    # Dans l'ordre croissant : chaque série prend la place libérée juste avant elle, sans heurter UNIQUE
    assert "numero_serie = numero_serie - 1" in renumerotation and "ORDER BY numero_serie" in renumerotation
    assert params == (7, 2)
    mock_db.commit.assert_called_once()


def test_supprimer_serie_inconnue_404(client):
    """DELETE /series/<id> pour une série qui n'existe pas doit retourner 404 serie_not_found, sans rien écrire."""
    res, mock_db, mock_cursor = supprimer_serie(client, 999, serie=None)

    assert res.status_code == 404
    assert res.get_json() == {"error": "serie_not_found"}
    assert not any(c[0][0].lstrip().startswith(("UPDATE", "DELETE")) for c in mock_cursor.execute.call_args_list)
    mock_db.commit.assert_not_called()


@pytest.mark.parametrize("methode", ["put", "delete"])
def test_series_erreur_db(client, methode):
    """PUT et DELETE /series/<id> : une erreur MySQL doit donner une 500 db_error en JSON et fermer la connexion."""
    mock_db = MagicMock()
    mock_db.cursor.return_value.execute.side_effect = mysql.connector.Error(msg="Lost connection")

    with patch("main.get_db", return_value=mock_db):
        res = getattr(client, methode)("/series/21", data=json.dumps({"poids_kg": 80, "repetitions": 6}),
                                       content_type="application/json")

    assert res.status_code == 500
    assert res.get_json()["error"] == "db_error"
    mock_db.close.assert_called_once()
