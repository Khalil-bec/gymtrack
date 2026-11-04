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
│  Nginx :8001     │────▶│  Flask API   │────▶│  MySQL 8.0  │
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
- Validation des champs + gestion des erreurs HTTP (400, 404, 409, 500)
- CORS configuré pour les appels depuis le frontend
- Jointures SQL multi-tables pour les endpoints de détail
- Connexion DB via variables d'environnement

**Côté tests :**
- Tests unitaires avec mocks, aucune dépendance à MySQL au moment des tests
- Cas couverts : succès, champs manquants, email facultatif, email invalide, email dupliqué, body vide, poids et dates invalides, client ou pesée introuvable (404)
- Le calcul du poids actuel et de son évolution sur 4 semaines est une fonction Python testée directement

**Côté frontend :**
- Interface pour coachs servie par Nginx : HTML/CSS/JS sans framework ni étape de build (modules ES)
- Navigation entre pages par l'adresse (`#/clients`, `#/clients/3` pour un profil, `#/exercices`)
- Graphique du poids de corps avec Chart.js (version exacte 4.6.1, vérifiée par empreinte `integrity`) et sa vue en tableau
- Adresse de l'API dans un seul fichier, `frontend/config.js`
- Formulaires en fenêtres `<dialog>` avec erreurs affichées sous le champ, messages temporaires au lieu d'`alert()`
- Toutes les valeurs venant de l'API sont insérées comme du texte (aucun HTML injecté)

---

## Schéma de la base de données

```
athletes ──< seances ──< exercice_logs ──< series
    └─────< pesees
exercices   (liste partagée ; pas encore reliée aux séances)
```

6 tables (5 reliées par clés étrangères, `exercices` pas encore), contraintes UNIQUE sur l'email et le nom d'exercice (sans tenir compte des majuscules ni des accents), et données de test insérées au démarrage.

---

## API — Endpoints

| Méthode | Route | Description |
|---|---|---|
| GET | `/health` | Statut de l'API |
| GET | `/athletes` | Liste des athlètes (clients), avec date de dernière séance, nombre de séances sur 4 semaines, poids actuel et évolution sur 4 semaines |
| POST | `/athletes` | Créer un athlète (nom obligatoire ; email facultatif, unique s'il est donné ; poids_kg facultatif, enregistré comme première pesée du jour) |
| GET | `/athletes/<id>` | Profil d'un athlète : infos, résumé des séances, poids actuel et évolution (404 si inconnu) |
| PUT | `/athletes/<id>` | Modifier le nom et l'email d'un athlète (mêmes règles qu'à la création ; email vide = effacé ; 404 si inconnu). Pas de suppression : elle effacerait l'historique |
| GET | `/athletes/<id>/pesees` | Pesées d'un athlète, de la plus ancienne à la plus récente |
| POST | `/athletes/<id>/pesees` | Ajouter une pesée (date_pesee, poids_kg) |
| DELETE | `/pesees/<id>` | Supprimer une pesée |
| GET | `/exercices` | Liste partagée des exercices (nom, type `charge` ou `poids_du_corps`, nombre de séances qui l'utilisent), triée par nom |
| POST | `/exercices` | Ajouter un exercice (nom, type ; 409 si le nom existe déjà). Pas de modification ni de suppression |
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
| Interface | http://localhost:8001 |
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