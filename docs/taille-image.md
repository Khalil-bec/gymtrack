# Taille de l'image : de 360 Mo à 137 Mo (app GymTrack)

## Résultat

| Étape | Dockerfile | Image de base | Espace disque | Taille du contenu |
|---|---|---|---|---|
| Départ (`gt-before`) | mono-étape | `python:3.11-slim` | 360 Mo | 98,5 Mo |
| Après le multi-étapes | multi-étapes | `python:3.11-slim` | 329 Mo | 78,6 Mo |
| Après le changement de base (`gymtrack-app`) | multi-étapes | `python:3.11-alpine` | **137 Mo** | **31,8 Mo** |

| Changement | Gain (espace disque) |
|---|---|
| 1. Build multi-étapes | -31 Mo (environ -9 %) |
| 2. Base `slim` → `alpine` | -192 Mo (environ -58 %) |
| Total | **-223 Mo (environ -62 %)**, contenu : -66,7 Mo (environ -68 %) |

Le build multi-étapes retire les étapes de construction de l'image livrée. Le changement de base a le plus gros effet, parce que l'image de base pèse plus de la moitié de l'image finale.

## Méthode de mesure

- Mesuré  avec `docker image ls`. Les tailles varient quand un tag de base évolue.
- « Départ » : le Dockerfile  reconstruit en `gt-before`.
- « Après le changement de base » : l'image `gymtrack-app` reconstruite avec `docker compose build --no-cache app`, puis le conteneur recréé avec `docker compose up -d app`.


Reconstruire l'image de départ sans toucher à l'arbre de travail :

```sh
git show '2cbdc15^:app/Dockerfile' | docker build -f - -t gt-before ./app
docker image ls gt-before
docker image ls gymtrack-app
```

## Changement 1 : build multi-étapes

```diff
-FROM python:3.11-slim
+FROM python:3.11-slim AS builder

 WORKDIR /app

 COPY requirements.txt .
-RUN pip install -r requirements.txt
+RUN python -m venv venv
+RUN venv/bin/pip install --upgrade pip
+RUN venv/bin/pip install -r requirements.txt
+
+FROM python:3.11-slim
+COPY main.py .
+COPY --from=builder /app/venv /app/venv
+ENV PATH="/app/venv/bin:$PATH"

-COPY . .
-
 EXPOSE 5000
```

L'étape `builder` exécute `pip install` dans un environnement virtuel. Le second `FROM` repart d'une image vierge et ne copie que `/app/venv` et `main.py`. Le reste de l'étape `builder` reste dans le cache de build et ne fait pas partie de l'image livrée. `COPY . .` a disparu : seul `main.py` est copié.

## Changement 2 : base `slim` → `alpine`

```diff
-FROM python:3.11-slim AS builder
+FROM python:3.11-alpine AS builder
 ...
-FROM python:3.11-slim
+FROM python:3.11-alpine
```

Le diff complet depuis le départ : `git diff '2cbdc15^' HEAD -- app/Dockerfile`.

## Vérification de l'image Alpine

L'import des paquets ne suffit pas à prouver que l'app fonctionne. J'ai donc lancé l'image Alpine et l'image `slim` côte à côte, chacune contre une base MySQL 8.0 jetable créée avec `db/init/01-schema.sql` (la vraie base et le volume `db-data` n'ont pas été touchés). Résultats identiques sur les deux images :

- `GET` `/health`, `/athletes`, `/seances`, `/seances/1` : 200.
- `POST /athletes` : 201 (valide), 409 (e-mail en double), 400 (champ manquant).
- `POST /seances` : 201 (valide), 400 (champ manquant).
- Les accents (`Éloïse Çà`) sont enregistrés et relus à l'identique (utf8mb4).

Puis sur la vraie stack, après recréation du conteneur : `docker compose ps` indique `healthy`, l'image du conteneur est bien la nouvelle (même identifiant que `docker image ls gymtrack-app`), et `GET /athletes` renvoie 200.


