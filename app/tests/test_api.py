
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
