# app/main.py
from flask import Flask, jsonify , request 
from flask_cors import CORS
import mysql.connector
import os

app = Flask(__name__)
CORS(app)
# La fonction get_db() permet d'obtenir une nouvelle connexion à la base de données MySQL. 
# Elle utilise les variables d'environnement pour les paramètres de connexion,
# avec des valeurs par défaut adaptées au conteneur Docker défini dans docker-compose.yml.

def get_db():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "gymtrack-db"),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", "root123"),
        database=os.getenv("DB_NAME", "gymtrack"),
        charset="utf8mb4",
        collation="utf8mb4_0900_ai_ci",
        use_unicode=True
    )

    
# La route /health est une simple route de test qui renvoie un statut "ok" en réponse JSON.
@app.route("/health")
def health():
    return jsonify({"status": "ok"})


# La route /athletes est une route qui permet de récupérer tous les athlètes de la base de données.
@app.route("/athletes")
def get_athletes():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM athletes")
    athletes = cursor.fetchall()
    db.close()
    return jsonify(athletes)


# la route /athletes qui permet de creer  une nouvelle athlete
@app.route("/athletes", methods=["POST"])
def create_athlete():
    data = request.get_json(silent=True) or {}

    nom = (data.get("nom") or "").strip()
    email = (data.get("email") or "").strip().lower()
    poids_kg = data.get("poids_kg")

    missing = []
    if not nom:
        missing.append("nom")
    if not email:
        missing.append("email")
    if missing:
        return jsonify({"error": "missing_fields", "missing": missing}), 400

    if poids_kg is not None:
        try:
            poids_kg = float(poids_kg)
        except (TypeError, ValueError):
            return jsonify({"error": "invalid_field", "field": "poids_kg"}), 400

    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            "INSERT INTO athletes (nom, email, poids_kg) VALUES (%s, %s, %s)",
            (nom, email, poids_kg)
        )
        db.commit()
        return jsonify({"id": cursor.lastrowid}), 201
    except mysql.connector.IntegrityError:
        return jsonify({"error": "email_already_exists"}), 409
    except mysql.connector.MySQLError as e:
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