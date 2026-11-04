# app/main.py
from flask import Flask, jsonify , request
from flask.json.provider import DefaultJSONProvider
from flask_cors import CORS
import mysql.connector
from mysql.connector.constants import ClientFlag
import datetime
import math
import os
import re

ER_DUP_ENTRY = 1062
ER_NO_REFERENCED_ROW = 1452  # clé étrangère vers une ligne qui n'existe pas
# Vérification simple : quelque chose@domaine.extension, sans espace
EMAIL_VALIDE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
# Longueurs maximales des colonnes nom (athletes, exercices) et athletes.email (db/init/01-schema.sql)
NOM_MAX = 100
EMAIL_MAX = 150
# Valeurs de exercices.type : avec charge ou au poids du corps
TYPES_EXERCICE = ("charge", "poids_du_corps")


# Les dates sortent en ISO 8601 ("2026-03-22") au lieu du format HTTP de Flask
# ("Sun, 22 Mar 2026 00:00:00 GMT"), plus simple à lire et à afficher côté frontend.
class JSONProvider(DefaultJSONProvider):
    @staticmethod
    def default(o):
        if isinstance(o, datetime.date):
            return o.isoformat()
        return DefaultJSONProvider.default(o)


# Lit un poids en kg : un nombre (ou du texte numérique) strictement entre 0 et 1000,
# la limite de la colonne DECIMAL(5,2). Renvoie None si la valeur n'est pas un poids valide.
def lire_poids(valeur):
    if isinstance(valeur, bool):
        return None
    try:
        poids = float(valeur)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(poids):
        return None
    # Arrondi au centième comme la colonne : 999.999 deviendrait 1000.00 (hors limites) et 0.001 deviendrait 0
    poids = round(poids, 2)
    if not 0 < poids < 1000:
        return None
    return poids


# Lit une date "AAAA-MM-JJ" ; None si ce n'est pas du texte ou pas une vraie date (ex. 30 février).
def lire_date(valeur):
    if not isinstance(valeur, str):
        return None
    try:
        return datetime.date.fromisoformat(valeur)
    except ValueError:
        return None


# Corps JSON de la requête ; {} s'il est absent, invalide ou n'est pas un objet (liste, texte…).
def lire_json():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


# Lit le champ "nom" (client ou exercice) : du texte, espaces répétés réduits à un seul
# (« Développé  couché » → « Développé couché », pour que la contrainte UNIQUE voie le doublon),
# au plus NOM_MAX caractères. Renvoie (nom, erreur) : nom vaut "" s'il manque ; erreur est le corps
# JSON d'une 400 ou None. Le cas « nom manquant » est laissé à l'appelant, qui liste ses champs manquants.
def lire_nom(data):
    valeur = data.get("nom")
    if valeur is not None and not isinstance(valeur, str):
        return "", {"error": "invalid_field", "field": "nom"}
    nom = " ".join((valeur or "").split())
    # Même limite que la colonne (VARCHAR) : sinon MySQL refuse et on renverrait une 500
    if len(nom) > NOM_MAX:
        return "", {"error": "invalid_field", "field": "nom"}
    return nom, None


# Lit et nettoie le nom et l'email d'un client (création et modification).
# Renvoie (nom, email, erreur) : erreur est le corps JSON d'une 400, ou None si tout est valide.
def lire_infos_athlete(data):
    if data.get("email") is not None and not isinstance(data["email"], str):
        return None, None, {"error": "invalid_field", "field": "email"}
    nom, erreur = lire_nom(data)
    if erreur:
        return None, None, erreur

    # L'email est facultatif : vide → NULL, pour que la contrainte UNIQUE ignore les clients sans email
    email = (data.get("email") or "").strip().lower() or None

    if not nom:
        return None, None, {"error": "missing_fields", "missing": ["nom"]}
    if email is not None and (len(email) > EMAIL_MAX or not EMAIL_VALIDE.match(email)):
        return None, None, {"error": "invalid_field", "field": "email"}
    return nom, email, None


# Poids actuel = dernière pesée ; évolution = dernière pesée − la plus récente pesée
# datée au plus tard 28 jours avant aujourd'hui (None s'il n'y en a pas).
# Les pesées datées après aujourd'hui sont ignorées, comme les séances futures.
# Deux pesées le même jour : la dernière saisie (id le plus grand) compte, comme sur le graphique.
def resume_poids(pesees, aujourdhui):
    triees = sorted(
        (pesee for pesee in pesees if pesee["date_pesee"] <= aujourdhui),
        key=lambda pesee: (pesee["date_pesee"], pesee.get("id", 0)),
    )
    if not triees:
        return {"poids_actuel": None, "evolution_4_semaines": None}
    actuel = float(triees[-1]["poids_kg"])
    limite = aujourdhui - datetime.timedelta(days=28)
    anciennes = [pesee for pesee in triees if pesee["date_pesee"] <= limite]
    # Si la dernière pesée est elle-même ancienne, il n'y a rien à comparer sur 4 semaines
    if not anciennes or anciennes[-1] is triees[-1]:
        return {"poids_actuel": actuel, "evolution_4_semaines": None}
    evolution = round(actuel - float(anciennes[-1]["poids_kg"]), 2)
    return {"poids_actuel": actuel, "evolution_4_semaines": evolution}


app = Flask(__name__)
app.json = JSONProvider(app)
CORS(app)
# La fonction get_db() permet d'obtenir une nouvelle connexion à la base de données MySQL. 
# Elle utilise les variables d'environnement pour les paramètres de connexion,
# avec des valeurs par défaut adaptées au conteneur Docker défini dans docker-compose.yml.

def get_db():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "gymtrack-db"),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME", "gymtrack"),
        charset="utf8mb4",
        collation="utf8mb4_0900_ai_ci",
        use_unicode=True,
        # rowcount d'un UPDATE = lignes trouvées, pas seulement modifiées : enregistrer un client
        # sans rien changer donne 1, pas 0, et 0 veut donc bien dire « client inconnu ».
        client_flags=[ClientFlag.FOUND_ROWS]
    )

    
# La route /health est une simple route de test qui renvoie un statut "ok" en réponse JSON.
@app.route("/health")
def health():
    return jsonify({"status": "ok"})


# La route /athletes renvoie tous les athlètes (les "clients" de l'interface),
# avec pour chacun la date de sa dernière séance, le nombre de séances sur les 4 dernières semaines,
# le poids actuel et son évolution sur 4 semaines.
@app.route("/athletes")
def get_athletes():
    db = None
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("""
            SELECT a.*, CURDATE() AS aujourdhui,
                   MAX(CASE WHEN s.date_seance <= CURDATE() THEN s.date_seance END) AS derniere_seance,
                   COUNT(CASE WHEN s.date_seance > CURDATE() - INTERVAL 28 DAY AND s.date_seance <= CURDATE() THEN 1 END) AS seances_4_semaines
            FROM athletes a
            LEFT JOIN seances s ON s.athlete_id = a.id
            GROUP BY a.id
            ORDER BY a.nom
        """)
        athletes = cursor.fetchall()
        cursor.execute("SELECT id, athlete_id, date_pesee, poids_kg FROM pesees")
        pesees_par_athlete = {}
        for pesee in cursor.fetchall():
            pesees_par_athlete.setdefault(pesee["athlete_id"], []).append(pesee)
        for athlete in athletes:
            aujourdhui = athlete.pop("aujourdhui")
            athlete.update(resume_poids(pesees_par_athlete.get(athlete["id"], []), aujourdhui))
        return jsonify(athletes)
    except mysql.connector.Error as e:
        return jsonify({"error": "db_error", "message": str(e)}), 500
    finally:
        if db is not None:
            db.close()


# La route /athletes/<id> renvoie le profil d'un client : ses infos, le résumé de ses séances
# et son poids actuel avec l'évolution sur 4 semaines (calculés par resume_poids).
@app.route("/athletes/<int:athlete_id>")
def get_athlete(athlete_id):
    db = None
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        # CURDATE() vient de MySQL : la même date de référence que pour les séances
        cursor.execute("""
            SELECT a.id, a.nom, a.email, a.created_at, CURDATE() AS aujourdhui,
                   MAX(CASE WHEN s.date_seance <= CURDATE() THEN s.date_seance END) AS derniere_seance,
                   COUNT(CASE WHEN s.date_seance > CURDATE() - INTERVAL 28 DAY AND s.date_seance <= CURDATE() THEN 1 END) AS seances_4_semaines
            FROM athletes a
            LEFT JOIN seances s ON s.athlete_id = a.id
            WHERE a.id = %s
            GROUP BY a.id
        """, (athlete_id,))
        athlete = cursor.fetchone()
        if athlete is None:
            return jsonify({"error": "athlete_not_found"}), 404
        cursor.execute(
            "SELECT id, date_pesee, poids_kg FROM pesees WHERE athlete_id = %s",
            (athlete_id,)
        )
        aujourdhui = athlete.pop("aujourdhui")
        athlete.update(resume_poids(cursor.fetchall(), aujourdhui))
        return jsonify(athlete)
    except mysql.connector.Error as e:
        return jsonify({"error": "db_error", "message": str(e)}), 500
    finally:
        if db is not None:
            db.close()


# la route /athletes qui permet de creer  une nouvelle athlete
@app.route("/athletes", methods=["POST"])
def create_athlete():
    data = lire_json()

    nom, email, erreur = lire_infos_athlete(data)
    if erreur:
        return jsonify(erreur), 400

    poids_kg = data.get("poids_kg")
    if poids_kg is not None:
        poids_kg = lire_poids(poids_kg)
        if poids_kg is None:
            return jsonify({"error": "invalid_field", "field": "poids_kg"}), 400

    db = None
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            "INSERT INTO athletes (nom, email) VALUES (%s, %s)",
            (nom, email)
        )
        athlete_id = cursor.lastrowid
        # Le poids de départ devient la première pesée, datée d'aujourd'hui (même transaction)
        if poids_kg is not None:
            cursor.execute(
                "INSERT INTO pesees (athlete_id, date_pesee, poids_kg) VALUES (%s, CURDATE(), %s)",
                (athlete_id, poids_kg)
            )
        db.commit()
        return jsonify({"id": athlete_id}), 201
    except mysql.connector.IntegrityError as e:
        # 1062 = doublon sur une clé UNIQUE ; les autres violations de contrainte sont de vraies erreurs
        if e.errno == ER_DUP_ENTRY:
            return jsonify({"error": "email_already_exists"}), 409
        return jsonify({"error": "db_error", "message": str(e)}), 500
    except mysql.connector.Error as e:
        return jsonify({"error": "db_error", "message": str(e)}), 500
    finally:
        if db is not None:
            db.close()


# La route PUT /athletes/<id> modifie le nom et l'email d'un client (pour corriger une faute de frappe).
# Les clients ne se suppriment pas : ça effacerait tout leur historique.
@app.route("/athletes/<int:athlete_id>", methods=["PUT"])
def update_athlete(athlete_id):
    nom, email, erreur = lire_infos_athlete(lire_json())
    if erreur:
        return jsonify(erreur), 400

    db = None
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            "UPDATE athletes SET nom = %s, email = %s WHERE id = %s",
            (nom, email, athlete_id)
        )
        if cursor.rowcount == 0:
            return jsonify({"error": "athlete_not_found"}), 404
        db.commit()
        return jsonify({"id": athlete_id, "nom": nom, "email": email}), 200
    except mysql.connector.IntegrityError as e:
        if e.errno == ER_DUP_ENTRY:
            return jsonify({"error": "email_already_exists"}), 409
        return jsonify({"error": "db_error", "message": str(e)}), 500
    except mysql.connector.Error as e:
        return jsonify({"error": "db_error", "message": str(e)}), 500
    finally:
        if db is not None:
            db.close()


# --- Pesées ---

# La route /athletes/<id>/pesees renvoie les pesées d'un client, de la plus ancienne à la plus récente.
@app.route("/athletes/<int:athlete_id>/pesees")
def get_pesees(athlete_id):
    db = None
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT id FROM athletes WHERE id = %s", (athlete_id,))
        if cursor.fetchone() is None:
            return jsonify({"error": "athlete_not_found"}), 404
        cursor.execute(
            "SELECT id, date_pesee, poids_kg FROM pesees WHERE athlete_id = %s ORDER BY date_pesee, id",
            (athlete_id,)
        )
        # DECIMAL → nombre : sinon le JSON contient "80.50" (texte) et le graphique ne peut pas le tracer
        pesees = [{**pesee, "poids_kg": float(pesee["poids_kg"])} for pesee in cursor.fetchall()]
        return jsonify(pesees)
    except mysql.connector.Error as e:
        return jsonify({"error": "db_error", "message": str(e)}), 500
    finally:
        if db is not None:
            db.close()


# La route POST /athletes/<id>/pesees ajoute une pesée (date + poids) à un client.
@app.route("/athletes/<int:athlete_id>/pesees", methods=["POST"])
def create_pesee(athlete_id):
    data = lire_json()

    missing = [champ for champ in ("date_pesee", "poids_kg") if data.get(champ) in (None, "")]
    if missing:
        return jsonify({"error": "missing_fields", "missing": missing}), 400

    date_pesee = lire_date(data["date_pesee"])
    # Pas de pesée dans le futur ; un jour de marge car l'horloge du serveur (UTC) peut être
    # en retard d'un jour sur celle du coach (ex. 0 h 30 à Paris = 23 h 30 la veille en UTC).
    if date_pesee is None or date_pesee > datetime.date.today() + datetime.timedelta(days=1):
        return jsonify({"error": "invalid_field", "field": "date_pesee"}), 400
    poids_kg = lire_poids(data["poids_kg"])
    if poids_kg is None:
        return jsonify({"error": "invalid_field", "field": "poids_kg"}), 400

    db = None
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            "INSERT INTO pesees (athlete_id, date_pesee, poids_kg) VALUES (%s, %s, %s)",
            (athlete_id, date_pesee.isoformat(), poids_kg)
        )
        db.commit()
        return jsonify({"id": cursor.lastrowid}), 201
    except mysql.connector.IntegrityError as e:
        if e.errno == ER_NO_REFERENCED_ROW:
            return jsonify({"error": "athlete_not_found"}), 404
        return jsonify({"error": "db_error", "message": str(e)}), 500
    except mysql.connector.Error as e:
        return jsonify({"error": "db_error", "message": str(e)}), 500
    finally:
        if db is not None:
            db.close()


# La route DELETE /pesees/<id> supprime une pesée saisie par erreur.
@app.route("/pesees/<int:pesee_id>", methods=["DELETE"])
def delete_pesee(pesee_id):
    db = None
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute("DELETE FROM pesees WHERE id = %s", (pesee_id,))
        db.commit()
        if cursor.rowcount == 0:
            return jsonify({"error": "pesee_not_found"}), 404
        return "", 204
    except mysql.connector.Error as e:
        return jsonify({"error": "db_error", "message": str(e)}), 500
    finally:
        if db is not None:
            db.close()


# --- Exercices ---

# La route /exercices renvoie la liste partagée des exercices, triée par nom.
# nb_seances vaut 0 tant que les séances notent les exercices en texte libre ; il comptera
# les séances qui utilisent l'exercice quand exercice_logs le référencera (ticket 06).
@app.route("/exercices")
def get_exercices():
    db = None
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT id, nom, type, 0 AS nb_seances FROM exercices ORDER BY nom")
        return jsonify(cursor.fetchall())
    except mysql.connector.Error as e:
        return jsonify({"error": "db_error", "message": str(e)}), 500
    finally:
        if db is not None:
            db.close()


# La route POST /exercices ajoute un exercice (nom + type). On ne peut ni le modifier ni le supprimer :
# les graphiques de progression reposent sur des noms stables.
@app.route("/exercices", methods=["POST"])
def create_exercice():
    data = lire_json()

    nom, erreur = lire_nom(data)
    if erreur:
        return jsonify(erreur), 400
    type_exercice = data.get("type")
    # Un type qui n'est pas du texte (0, false, liste…) est invalide, pas manquant
    if type_exercice is not None and not isinstance(type_exercice, str):
        return jsonify({"error": "invalid_field", "field": "type"}), 400

    missing = [champ for champ, valeur in (("nom", nom), ("type", type_exercice)) if not valeur]
    if missing:
        return jsonify({"error": "missing_fields", "missing": missing}), 400
    if type_exercice not in TYPES_EXERCICE:
        return jsonify({"error": "invalid_field", "field": "type"}), 400

    db = None
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute("INSERT INTO exercices (nom, type) VALUES (%s, %s)", (nom, type_exercice))
        db.commit()
        return jsonify({"id": cursor.lastrowid, "nom": nom, "type": type_exercice, "nb_seances": 0}), 201
    except mysql.connector.IntegrityError as e:
        # 1062 = nom déjà pris ; la collation de la colonne ignore la casse et les accents
        if e.errno == ER_DUP_ENTRY:
            return jsonify({"error": "exercice_already_exists"}), 409
        return jsonify({"error": "db_error", "message": str(e)}), 500
    except mysql.connector.Error as e:
        return jsonify({"error": "db_error", "message": str(e)}), 500
    finally:
        if db is not None:
            db.close()


# La route /seances est une route qui permet de créer une nouvelle séance.
@app.route("/seances", methods=["POST"])
def create_seance():
    data = request.get_json(silent=True) or {}

    athlete_id = data.get("athlete_id")
    titre = data.get("titre")
    date_seance = data.get("date_seance")
    duree_min = data.get("duree_min")

    missing = [k for k in ("athlete_id", "titre", "date_seance") if not data.get(k)]
    if missing:
        return jsonify({"error": "missing_fields", "missing": missing}), 400

    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            "INSERT INTO seances (athlete_id, titre, date_seance, duree_min) VALUES (%s,%s,%s,%s)",
            (athlete_id, titre, date_seance, duree_min)
        )
        db.commit()
        new_id = cursor.lastrowid
        db.close()
        return jsonify({"id": new_id}), 201
    except mysql.connector.MySQLError as e:
        try:
            db.close()
        except Exception:
            pass
        return jsonify({"error": "db_error", "message": str(e)}), 500


# La route /seances est une route qui permet de récupérer toutes les séances de la base de données. 
@app.route("/seances")
def get_seances():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("""
        SELECT s.*, a.nom as athlete_nom
        FROM seances s
        JOIN athletes a ON s.athlete_id = a.id
        ORDER BY s.date_seance DESC
    """)
    seances = cursor.fetchall()
    db.close()
    return jsonify(seances)

# La route /seances/<int:seance_id> est une route qui permet de récupérer les détails d'une séance spécifique.
@app.route("/seances/<int:seance_id>")
def get_seance_detail(seance_id):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("""
        SELECT e.nom as exercice, s.numero_serie,
               s.poids_kg, s.repetitions, s.repos_sec
        FROM exercice_logs e
        JOIN series s ON s.exercice_id = e.id
        WHERE e.seance_id = %s
        ORDER BY e.ordre, s.numero_serie
    """, (seance_id,))
    detail = cursor.fetchall()
    db.close()
    return jsonify(detail)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)