# app/main.py
from flask import Flask, jsonify
import mysql.connector
import os

app = Flask(__name__)
# La fonction get_db() permet d'obtenir une nouvelle connexion à la base de données MySQL. 
# Elle utilise les variables d'environnement pour les paramètres de connexion,
# avec des valeurs par défaut adaptées au conteneur Docker défini dans docker-compose.yml.

def get_db():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "gymtrack-db"),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", "root123"),
        database=os.getenv("DB_NAME", "gymtrack")
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