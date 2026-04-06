# GymTrack

Application de suivi d'entraînement musculaire 

L'objectif n'est pas juste de faire tourner une app, c'est de construire une stack complète : API containerisée, base de données persistante, frontend servi par Nginx, CI/CD automatisée, tests isolés du reste. Chaque brique a été choisie et configurée à la main.

---

## Stack technique

| Couche | Techno |
|---|---|
| API | Python 3.11 · Flask · Flask-CORS |
| Base de données | MySQL 8.0 |
| Orchestration | Docker Compose |
| Reverse proxy / Frontend | Nginx (image alpine) |
| Tests | pytest · unittest.mock |
| CI/CD | GitHub Actions |
| UI Admin DB | Adminer |

---

## Architecture

```
┌──────────────────┐     ┌──────────────┐     ┌─────────────┐
│  Nginx :80       │────▶│  Flask API   │────▶│  MySQL 8.0  │
│  (frontend HTML) │     │  :5000       │     │  :3306      │
└──────────────────┘     └──────────────┘     └─────────────┘
                                                    │
                                             ┌─────────────┐
                                             │   Adminer   │
                                             │   :8080     │
                                             └─────────────┘
```

3 services distincts, chacun dans son propre conteneur. Le frontend est une image `nginx:alpine` qui sert les fichiers statiques — pas de serveur Python pour ça.

---

## Ce que le projet démontre

**Côté DevOps / infrastructure :**
- Healthcheck MySQL, l'API ne démarre que quand la DB est réellement prête (`condition: service_healthy`)
- Volume nommé pour la persistance des données entre les redémarrages
- Réseau bridge dédié pour l'isolation des conteneurs
- Variables d'environnement via `.env` (credentials hors du code)
- Init SQL automatique au démarrage via `/docker-entrypoint-initdb.d`
- CI GitHub Actions sur chaque push : tests pytest + vérification du build Docker
- Makefile avec raccourcis pour toutes les opérations courantes

**Côté API :**
- Validation des champs + gestion des erreurs HTTP (400, 409, 500)
- CORS configuré pour les appels depuis le frontend
- Jointures SQL multi-tables pour les endpoints de détail
- Connexion DB via variables d'environnement

**Côté tests :**
- Tests unitaires avec mocks, aucune dépendance à MySQL au moment des tests
- Cas couverts : succès, champs manquants, email dupliqué, body vide

**Côté frontend :**
- Dashboard interactif servi par Nginx
- Appels fetch vers l'API (GET + POST)
- Formulaires modaux Bootstrap avec gestion des erreurs réseau
- Graphique Chart.js (volume d'entraînement hebdomadaire)
- Affichage détaillé des séances : exercices, séries, poids, répétitions

---

## Schéma de la base de données

```
athletes ──< seances ──< exercice_logs ──< series
```

4 tables relationnelles avec clés étrangères, contrainte UNIQUE sur l'email, et données de test insérées au démarrage.

---

## API — Endpoints

| Méthode | Route | Description |
|---|---|---|
| GET | `/health` | Statut de l'API |
| GET | `/athletes` | Liste des athlètes |
| POST | `/athletes` | Créer un athlète (nom, email, poids_kg) |
| GET | `/seances` | Historique des séances avec nom de l'athlète |
| POST | `/seances` | Créer une séance |
| GET | `/seances/<id>` | Détail d'une séance — exercices + séries |

---

## Lancer le projet

```bash
git clone https://github.com/Khalil-bec/gymtrack.git
cd gymtrack
cp .env.exemple .env   # renseigner le mot de passe MySQL
docker compose up --build
```

| Service | URL |
|---|---|
| Dashboard | http://localhost:80 |
| API Flask | http://localhost:5000/health |
| Adminer | http://localhost:8080 |

---

## Commandes utiles

```bash
make up          # Lance toute la stack en arrière-plan
make test        # Lancer pytest dans le conteneur
make logs        # Suivre les logs en temps réel
make clean       # Supprimer les conteneurs et volumes
```

---

## Roadmap(To Do)

- Déploiement sur Oracle Cloud Free Tier

---

## Auteur

**Mohamed Khalil BECHEIKH**  
Étudiant en informatique  — UPPA  
Passionné par la culture DevOps et l'ingénierie système.

[![GitHub](https://img.shields.io/badge/GitHub-Khalil--bec-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/Khalil-bec)