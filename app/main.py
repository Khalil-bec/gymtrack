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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)