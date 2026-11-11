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
TITRE_MAX = 200   # seances.titre
DUREE_MAX = 600   # durée d'une séance en minutes (10 h)
ID_MAX = 2**31 - 1  # plus grand INT MySQL
REPS_MAX = 999      # répétitions d'une série
REPOS_MAX = 3600    # repos après une série, en secondes (1 h)
REPOS_DEFAUT = 90
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


# Lit un nombre entier entre minimum et maximum : un int, ou du texte de chiffres venant d'un formulaire ("75").
# Renvoie None sinon (75.5, "une heure", True — bool est un int en Python, mais True n'est pas 1 minute).
def lire_entier(valeur, minimum, maximum):
    # isdecimal et pas isdigit : « ² » est un « chiffre » pour isdigit mais int() le refuse
    # 10 chiffres au plus : assez pour un INT MySQL, et int() refuse au-delà de 4300 chiffres (ValueError)
    if isinstance(valeur, str) and valeur.strip().isdecimal() and len(valeur.strip()) <= 10:
        valeur = int(valeur)
    if isinstance(valeur, bool) or not isinstance(valeur, int) or not minimum <= valeur <= maximum:
        return None
    return valeur


# Comme lire_date, mais refuse aussi une date à venir (pesée, séance : on note ce qui a eu lieu).
# Un jour de marge, car l'horloge du serveur (UTC) peut être en retard d'un jour sur celle
# du coach (ex. 0 h 30 à Paris = 23 h 30 la veille en UTC).
def lire_date_passee(valeur):
    date = lire_date(valeur)
    if date is None or date > datetime.date.today() + datetime.timedelta(days=1):
        return None
    return date


# Lit et valide une séance (création et modification) : titre et date obligatoires, durée facultative
# en minutes (entier de 1 à 600, ou texte numérique venant du formulaire ; vide → NULL).
# Renvoie (titre, date, duree_min, erreur) : erreur est le corps JSON d'une 400, ou None.
def lire_infos_seance(data):
    if data.get("titre") is not None and not isinstance(data["titre"], str):
        return None, None, None, {"error": "invalid_field", "field": "titre"}
    titre = " ".join((data.get("titre") or "").split())

    missing = [champ for champ, valeur in (("titre", titre), ("date_seance", data.get("date_seance"))) if not valeur]
    if missing:
        return None, None, None, {"error": "missing_fields", "missing": missing}
    if len(titre) > TITRE_MAX:
        return None, None, None, {"error": "invalid_field", "field": "titre"}

    date_seance = lire_date_passee(data["date_seance"])
    if date_seance is None:
        return None, None, None, {"error": "invalid_field", "field": "date_seance"}

    duree_min = data.get("duree_min")
    if duree_min in (None, ""):
        duree_min = None
    else:
        duree_min = lire_entier(duree_min, 1, DUREE_MAX)
        if duree_min is None:
            return None, None, None, {"error": "invalid_field", "field": "duree_min"}
    return titre, date_seance, duree_min, None


# Lit et valide une série selon le type de l'exercice : poids obligatoire avec charge, interdit au poids
# du corps ; reps obligatoires (1 à REPS_MAX) ; repos facultatif en secondes (0 à REPOS_MAX) : absent, il vaut
# repos_defaut (90 s à l'ajout, le repos déjà enregistré quand on corrige une série).
# Renvoie (poids_kg, repetitions, repos_sec, erreur) : erreur est le corps JSON d'une 400, ou None.
def lire_infos_serie(data, type_exercice, repos_defaut=None):
    poids_donne = data.get("poids_kg") not in (None, "")
    missing = []
    if type_exercice == "charge" and not poids_donne:
        missing.append("poids_kg")
    if data.get("repetitions") in (None, ""):
        missing.append("repetitions")
    if missing:
        return None, None, None, {"error": "missing_fields", "missing": missing}

    poids_kg = None
    if poids_donne:
        # Un poids sur un exercice au poids du corps est une erreur de saisie, pas une valeur à ignorer
        poids_kg = lire_poids(data["poids_kg"]) if type_exercice == "charge" else None
        if poids_kg is None:
            return None, None, None, {"error": "invalid_field", "field": "poids_kg"}

    repetitions = lire_entier(data["repetitions"], 1, REPS_MAX)
    if repetitions is None:
        return None, None, None, {"error": "invalid_field", "field": "repetitions"}

    repos_sec = REPOS_DEFAUT if repos_defaut is None else repos_defaut
    if data.get("repos_sec") not in (None, ""):
        repos_sec = lire_entier(data["repos_sec"], 0, REPOS_MAX)
        if repos_sec is None:
            return None, None, None, {"error": "invalid_field", "field": "repos_sec"}
    return poids_kg, repetitions, repos_sec, None


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


# Vrai si la série a bat la série b : avec charge, la plus lourde (puis le plus de répétitions à poids égal) ;
# au poids du corps, le plus de répétitions.
def meilleure_serie(a, b, type_exercice):
    if type_exercice == "charge":
        return (a["poids_kg"], a["repetitions"]) > (b["poids_kg"], b["repetitions"])
    return a["repetitions"] > b["repetitions"]


# Progression d'un client : à partir de ses séries (une ligne par série, avec l'exercice et la séance),
# un point par séance et par exercice = la meilleure série de la séance.
# Les exercices gardent l'ordre des lignes (trié par la requête SQL) ; les points vont du plus ancien au plus récent.
def progression(lignes):
    exercices = {}
    for ligne in lignes:
        # Une série avec charge sans poids (possible seulement hors de l'API, par Adminer par exemple)
        # n'a pas de charge à comparer : on l'ignore plutôt que de planter
        if ligne["type"] == "charge" and ligne["poids_kg"] is None:
            continue
        exercice = exercices.setdefault(ligne["exercice_id"], {
            "exercice_id": ligne["exercice_id"], "nom": ligne["nom"], "type": ligne["type"], "meilleures": {},
        })
        point = {
            "seance_id": ligne["seance_id"], "date_seance": ligne["date_seance"],
            "poids_kg": None if ligne["poids_kg"] is None else float(ligne["poids_kg"]),
            "repetitions": ligne["repetitions"],
        }
        actuelle = exercice["meilleures"].get(ligne["seance_id"])
        if actuelle is None or meilleure_serie(point, actuelle, ligne["type"]):
            exercice["meilleures"][ligne["seance_id"]] = point
    resultat = []
    for exercice in exercices.values():
        points = sorted(exercice.pop("meilleures").values(), key=lambda p: (p["date_seance"], p["seance_id"]))
        resultat.append({**exercice, "points": points})
    return resultat


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

    
# La route /health est une route de santé pour vérifier que l'application peut se connecter à la base de données MySQL.
@app.route("/health")
def health():
    db = None
    try :
        db = get_db()
        db.cursor().execute("SELECT 1")
    except mysql.connector.Error as e:
        app.logger.error("Health check failed: %s", e)
        return jsonify({"status": "error", "message": "connection a la base de donnees echouee"}), 503
    finally:
        if db is not None:
            db.close()
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

    date_pesee = lire_date_passee(data["date_pesee"])
    if date_pesee is None:
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

# La route /exercices renvoie la liste partagée des exercices, triée par nom,
# avec le nombre de séances qui utilisent chacun.
@app.route("/exercices")
def get_exercices():
    db = None
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("""
            SELECT x.id, x.nom, x.type, COUNT(DISTINCT l.seance_id) AS nb_seances
            FROM exercices x
            LEFT JOIN exercice_logs l ON l.exercice_id = x.id
            GROUP BY x.id
            ORDER BY nom
        """)
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


# --- Séances ---

# La route /athletes/<id>/seances renvoie les séances d'un client, la plus récente d'abord,
# avec le nombre d'exercices notés dans chacune.
@app.route("/athletes/<int:athlete_id>/seances")
def get_seances_athlete(athlete_id):
    db = None
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT id FROM athletes WHERE id = %s", (athlete_id,))
        if cursor.fetchone() is None:
            return jsonify({"error": "athlete_not_found"}), 404
        cursor.execute("""
            SELECT s.id, s.titre, s.date_seance, s.duree_min, COUNT(e.id) AS nb_exercices
            FROM seances s
            LEFT JOIN exercice_logs e ON e.seance_id = s.id
            WHERE s.athlete_id = %s
            GROUP BY s.id
            ORDER BY s.date_seance DESC, s.id DESC
        """, (athlete_id,))
        return jsonify(cursor.fetchall())
    except mysql.connector.Error as e:
        return jsonify({"error": "db_error", "message": str(e)}), 500
    finally:
        if db is not None:
            db.close()


# La route /athletes/<id>/progression renvoie, pour chaque exercice où ce client a noté au moins une série
# (triés par nom), un point par séance : la meilleure série (voir progression), du plus ancien au plus récent.
@app.route("/athletes/<int:athlete_id>/progression")
def get_progression(athlete_id):
    db = None
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT id FROM athletes WHERE id = %s", (athlete_id,))
        if cursor.fetchone() is None:
            return jsonify({"error": "athlete_not_found"}), 404
        cursor.execute("""
            SELECT x.id AS exercice_id, x.nom, x.type, s.id AS seance_id, s.date_seance,
                   r.poids_kg, r.repetitions
            FROM seances s
            JOIN exercice_logs l ON l.seance_id = s.id
            JOIN exercices x ON x.id = l.exercice_id
            JOIN series r ON r.exercice_log_id = l.id
            WHERE s.athlete_id = %s
            ORDER BY x.nom, x.id
        """, (athlete_id,))
        return jsonify(progression(cursor.fetchall()))
    except mysql.connector.Error as e:
        return jsonify({"error": "db_error", "message": str(e)}), 500
    finally:
        if db is not None:
            db.close()


# La route POST /athletes/<id>/seances crée une séance pour ce client : le client vient de l'URL
# (la page profil), jamais du formulaire. Titre et date obligatoires, durée facultative.
@app.route("/athletes/<int:athlete_id>/seances", methods=["POST"])
def create_seance(athlete_id):
    titre, date_seance, duree_min, erreur = lire_infos_seance(lire_json())
    if erreur:
        return jsonify(erreur), 400

    db = None
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            "INSERT INTO seances (athlete_id, titre, date_seance, duree_min) VALUES (%s, %s, %s, %s)",
            (athlete_id, titre, date_seance.isoformat(), duree_min)
        )
        db.commit()
        return jsonify({"id": cursor.lastrowid}), 201
    except mysql.connector.IntegrityError as e:
        # 1452 = clé étrangère vers un client qui n'existe pas
        if e.errno == ER_NO_REFERENCED_ROW:
            return jsonify({"error": "athlete_not_found"}), 404
        return jsonify({"error": "db_error", "message": str(e)}), 500
    except mysql.connector.Error as e:
        return jsonify({"error": "db_error", "message": str(e)}), 500
    finally:
        if db is not None:
            db.close()


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

# La route /seances/<id> renvoie une séance : en-tête (titre, date, durée, client) et exercices notés
# dans l'ordre d'ajout, chacun avec son type et ses séries dans l'ordre.
@app.route("/seances/<int:seance_id>")
def get_seance(seance_id):
    db = None
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("""
            SELECT s.id, s.titre, s.date_seance, s.duree_min, s.athlete_id, a.nom AS athlete_nom
            FROM seances s
            JOIN athletes a ON a.id = s.athlete_id
            WHERE s.id = %s
        """, (seance_id,))
        seance = cursor.fetchone()
        if seance is None:
            return jsonify({"error": "seance_not_found"}), 404

        # Une ligne par série ; un exercice encore sans série donne une ligne avec serie_id vide
        cursor.execute("""
            SELECT l.id AS log_id, l.exercice_id, x.nom, x.type, l.ordre,
                   s.id AS serie_id, s.numero_serie, s.poids_kg, s.repetitions, s.repos_sec
            FROM exercice_logs l
            JOIN exercices x ON x.id = l.exercice_id
            LEFT JOIN series s ON s.exercice_log_id = l.id
            WHERE l.seance_id = %s
            ORDER BY l.ordre, l.id, s.numero_serie
        """, (seance_id,))
        exercices = {}
        for ligne in cursor.fetchall():
            exercice = exercices.setdefault(ligne["log_id"], {
                "id": ligne["log_id"], "exercice_id": ligne["exercice_id"],
                "nom": ligne["nom"], "type": ligne["type"], "series": [],
            })
            if ligne["serie_id"] is not None:
                exercice["series"].append({
                    "id": ligne["serie_id"], "numero_serie": ligne["numero_serie"],
                    # DECIMAL → nombre (comme pour les pesées) ; vide au poids du corps
                    "poids_kg": None if ligne["poids_kg"] is None else float(ligne["poids_kg"]),
                    "repetitions": ligne["repetitions"], "repos_sec": ligne["repos_sec"],
                })
        # Les dict gardent l'ordre d'insertion, donc l'ordre de la requête
        seance["exercices"] = list(exercices.values())
        return jsonify(seance)
    except mysql.connector.Error as e:
        return jsonify({"error": "db_error", "message": str(e)}), 500
    finally:
        if db is not None:
            db.close()


# La route POST /seances/<id>/exercices ajoute un exercice de la liste à la fin de la séance.
# Un exercice n'apparaît qu'une fois par séance : ses séries se notent toutes sous la même entrée.
@app.route("/seances/<int:seance_id>/exercices", methods=["POST"])
def ajouter_exercice_seance(seance_id):
    data = lire_json()
    if data.get("exercice_id") in (None, ""):
        return jsonify({"error": "missing_fields", "missing": ["exercice_id"]}), 400
    exercice_id = lire_entier(data["exercice_id"], 1, ID_MAX)
    if exercice_id is None:
        return jsonify({"error": "invalid_field", "field": "exercice_id"}), 400

    db = None
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        # Séance vérifiée à part : sinon une clé étrangère refusée ne dirait pas si c'est la séance ou l'exercice.
        # FOR UPDATE la verrouille jusqu'au commit : deux ajouts simultanés ne calculent pas le même ordre.
        cursor.execute("SELECT id FROM seances WHERE id = %s FOR UPDATE", (seance_id,))
        if cursor.fetchone() is None:
            return jsonify({"error": "seance_not_found"}), 404
        cursor.execute("""
            INSERT INTO exercice_logs (seance_id, exercice_id, ordre)
            SELECT %s, %s, COALESCE(MAX(ordre), 0) + 1 FROM exercice_logs WHERE seance_id = %s
        """, (seance_id, exercice_id, seance_id))
        db.commit()
        return jsonify({"id": cursor.lastrowid}), 201
    except mysql.connector.IntegrityError as e:
        if e.errno == ER_NO_REFERENCED_ROW:
            return jsonify({"error": "invalid_field", "field": "exercice_id"}), 400
        if e.errno == ER_DUP_ENTRY:
            return jsonify({"error": "exercice_deja_dans_seance"}), 409
        return jsonify({"error": "db_error", "message": str(e)}), 500
    except mysql.connector.Error as e:
        return jsonify({"error": "db_error", "message": str(e)}), 500
    finally:
        if db is not None:
            db.close()


# La route POST /exercice-logs/<id>/series enregistre une série dès qu'elle est saisie,
# numérotée à la suite des séries déjà notées pour cet exercice dans la séance.
@app.route("/exercice-logs/<int:log_id>/series", methods=["POST"])
def ajouter_serie(log_id):
    data = lire_json()

    db = None
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        # Le type de l'exercice décide si le poids est obligatoire ou interdit. FOR UPDATE verrouille l'exercice
        # noté jusqu'au commit : deux séries envoyées en même temps ne calculent pas le même numéro.
        cursor.execute("""
            SELECT x.type FROM exercice_logs l JOIN exercices x ON x.id = l.exercice_id WHERE l.id = %s FOR UPDATE OF l
        """, (log_id,))
        exercice = cursor.fetchone()
        if exercice is None:
            return jsonify({"error": "exercice_log_not_found"}), 404

        poids_kg, repetitions, repos_sec, erreur = lire_infos_serie(data, exercice["type"])
        if erreur:
            return jsonify(erreur), 400

        cursor.execute(
            "SELECT COALESCE(MAX(numero_serie), 0) + 1 AS suivant FROM series WHERE exercice_log_id = %s", (log_id,)
        )
        numero_serie = cursor.fetchone()["suivant"]
        cursor.execute(
            "INSERT INTO series (exercice_log_id, numero_serie, poids_kg, repetitions, repos_sec) VALUES (%s, %s, %s, %s, %s)",
            (log_id, numero_serie, poids_kg, repetitions, repos_sec)
        )
        serie_id = cursor.lastrowid
        db.commit()
        return jsonify({
            "id": serie_id, "numero_serie": numero_serie,
            "poids_kg": poids_kg, "repetitions": repetitions, "repos_sec": repos_sec,
        }), 201
    except mysql.connector.Error as e:
        return jsonify({"error": "db_error", "message": str(e)}), 500
    finally:
        if db is not None:
            db.close()


# Verrouille une série pour la corriger ou la supprimer, dans le même ordre que l'ajout d'une série :
# d'abord son exercice noté, puis la série elle-même. Un ordre différent pourrait interbloquer deux
# requêtes simultanées (ajout et suppression sur le même exercice). La série est relue une fois le verrou
# obtenu : une autre requête a pu la supprimer ou la renuméroter entre-temps.
# Renvoie {exercice_log_id, type, numero_serie, repos_sec}, ou None si la série n'existe pas (ou plus).
def verrouiller_serie(cursor, serie_id):
    cursor.execute("SELECT exercice_log_id FROM series WHERE id = %s", (serie_id,))
    serie = cursor.fetchone()
    if serie is None:
        return None
    cursor.execute("""
        SELECT x.type FROM exercice_logs l JOIN exercices x ON x.id = l.exercice_id WHERE l.id = %s FOR UPDATE OF l
    """, (serie["exercice_log_id"],))
    exercice = cursor.fetchone()
    cursor.execute("SELECT numero_serie, repos_sec FROM series WHERE id = %s FOR UPDATE", (serie_id,))
    verrouillee = cursor.fetchone()
    if exercice is None or verrouillee is None:
        return None
    return {"exercice_log_id": serie["exercice_log_id"], "type": exercice["type"], **verrouillee}


# La route PUT /series/<id> corrige une série enregistrée (poids, reps, repos), avec les mêmes règles
# qu'à l'ajout ; un repos laissé vide garde l'ancien. Son numéro ne change pas.
@app.route("/series/<int:serie_id>", methods=["PUT"])
def modifier_serie(serie_id):
    data = lire_json()

    db = None
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        serie = verrouiller_serie(cursor, serie_id)
        if serie is None:
            return jsonify({"error": "serie_not_found"}), 404

        poids_kg, repetitions, repos_sec, erreur = lire_infos_serie(data, serie["type"], repos_defaut=serie["repos_sec"])
        if erreur:
            return jsonify(erreur), 400

        cursor.execute(
            "UPDATE series SET poids_kg = %s, repetitions = %s, repos_sec = %s WHERE id = %s",
            (poids_kg, repetitions, repos_sec, serie_id)
        )
        db.commit()
        return jsonify({
            "id": serie_id, "numero_serie": serie["numero_serie"],
            "poids_kg": poids_kg, "repetitions": repetitions, "repos_sec": repos_sec,
        })
    except mysql.connector.Error as e:
        return jsonify({"error": "db_error", "message": str(e)}), 500
    finally:
        if db is not None:
            db.close()


# La route DELETE /series/<id> supprime une série saisie par erreur et renumérote les suivantes
# du même exercice, pour que la numérotation reste continue (1, 2, 3…).
@app.route("/series/<int:serie_id>", methods=["DELETE"])
def supprimer_serie(serie_id):
    db = None
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        serie = verrouiller_serie(cursor, serie_id)
        if serie is None:
            return jsonify({"error": "serie_not_found"}), 404

        cursor.execute("DELETE FROM series WHERE id = %s", (serie_id,))
        # Ordre croissant : chaque série descend dans la place libérée juste avant elle, sans jamais
        # prendre un numéro encore utilisé (contrainte UNIQUE exercice_log_id + numero_serie)
        cursor.execute("""
            UPDATE series SET numero_serie = numero_serie - 1
            WHERE exercice_log_id = %s AND numero_serie > %s
            ORDER BY numero_serie
        """, (serie["exercice_log_id"], serie["numero_serie"]))
        db.commit()
        return "", 204
    except mysql.connector.Error as e:
        return jsonify({"error": "db_error", "message": str(e)}), 500
    finally:
        if db is not None:
            db.close()


# La route PUT /seances/<id> modifie le titre, la date et la durée d'une séance
# (la durée peut être ajoutée après coup). Mêmes règles qu'à la création.
@app.route("/seances/<int:seance_id>", methods=["PUT"])
def update_seance(seance_id):
    titre, date_seance, duree_min, erreur = lire_infos_seance(lire_json())
    if erreur:
        return jsonify(erreur), 400

    db = None
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            "UPDATE seances SET titre = %s, date_seance = %s, duree_min = %s WHERE id = %s",
            (titre, date_seance.isoformat(), duree_min, seance_id)
        )
        # rowcount = lignes trouvées (FOUND_ROWS dans get_db) : 0 veut dire séance inconnue
        if cursor.rowcount == 0:
            return jsonify({"error": "seance_not_found"}), 404
        db.commit()
        return jsonify({"id": seance_id, "titre": titre, "date_seance": date_seance, "duree_min": duree_min})
    except mysql.connector.Error as e:
        return jsonify({"error": "db_error", "message": str(e)}), 500
    finally:
        if db is not None:
            db.close()


# La route DELETE /seances/<id> supprime une séance ; ses exercices notés et leurs séries
# partent avec elle (ON DELETE CASCADE dans le schéma).
@app.route("/seances/<int:seance_id>", methods=["DELETE"])
def delete_seance(seance_id):
    db = None
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute("DELETE FROM seances WHERE id = %s", (seance_id,))
        if cursor.rowcount == 0:
            return jsonify({"error": "seance_not_found"}), 404
        db.commit()
        return "", 204
    except mysql.connector.Error as e:
        return jsonify({"error": "db_error", "message": str(e)}), 500
    finally:
        if db is not None:
            db.close()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)