SET NAMES utf8mb4 COLLATE utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS athletes (
  id         INT AUTO_INCREMENT PRIMARY KEY,
  nom        VARCHAR(100) NOT NULL,
  email      VARCHAR(150) UNIQUE,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Pesées : le poids de corps d'un client dans le temps (le poids actuel = la dernière pesée)
CREATE TABLE IF NOT EXISTS pesees (
  id          INT AUTO_INCREMENT PRIMARY KEY,
  athlete_id  INT NOT NULL,
  date_pesee  DATE NOT NULL,
  poids_kg    DECIMAL(5,2) NOT NULL,
  created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (athlete_id) REFERENCES athletes(id)
);

-- Exercices : la liste partagée par toutes les séances (on peut seulement en ajouter).
-- La collation ignore la casse et les accents : « developpe couche » est un doublon de « Développé couché ».
CREATE TABLE IF NOT EXISTS exercices (
  id          INT AUTO_INCREMENT PRIMARY KEY,
  nom         VARCHAR(100) COLLATE utf8mb4_0900_ai_ci NOT NULL UNIQUE,
  type        ENUM('charge', 'poids_du_corps') NOT NULL,
  created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS seances (
  id          INT AUTO_INCREMENT PRIMARY KEY,
  athlete_id  INT NOT NULL,
  titre       VARCHAR(200) NOT NULL,
  date_seance DATE NOT NULL,
  duree_min   INT,
  notes       TEXT,
  created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (athlete_id) REFERENCES athletes(id)
);

-- Exercices notés dans une séance : un exercice de la liste, au plus une fois par séance, dans l'ordre d'ajout
CREATE TABLE IF NOT EXISTS exercice_logs (
  id           INT AUTO_INCREMENT PRIMARY KEY,
  seance_id    INT NOT NULL,
  exercice_id  INT NOT NULL,
  ordre        INT NOT NULL,
  UNIQUE (seance_id, exercice_id),
  -- Supprimer une séance supprime ses exercices notés (et, en cascade, leurs séries)
  FOREIGN KEY (seance_id) REFERENCES seances(id) ON DELETE CASCADE,
  FOREIGN KEY (exercice_id) REFERENCES exercices(id)
);

-- Séries d'un exercice noté, numérotées 1, 2, 3… ; poids_kg vide pour un exercice au poids du corps
CREATE TABLE IF NOT EXISTS series (
  id               INT AUTO_INCREMENT PRIMARY KEY,
  exercice_log_id  INT NOT NULL,
  numero_serie     INT NOT NULL,
  poids_kg         DECIMAL(5,2),
  repetitions      INT NOT NULL,
  repos_sec        INT NOT NULL DEFAULT 90,
  UNIQUE (exercice_log_id, numero_serie),
  FOREIGN KEY (exercice_log_id) REFERENCES exercice_logs(id) ON DELETE CASCADE
);

-- Liste d'exercices de départ (les données de démo sont dans 02-donnees-demo.sql)
-- Ids explicites : 02-donnees-demo.sql y fait référence
INSERT INTO exercices (id, nom, type) VALUES
  (1, 'Développé couché', 'charge'),
  (2, 'Développé incliné haltères', 'charge'),
  (3, 'Développé militaire', 'charge'),
  (4, 'Élévations latérales', 'charge'),
  (5, 'Squat', 'charge'),
  (6, 'Soulevé de terre', 'charge'),
  (7, 'Presse à cuisses', 'charge'),
  (8, 'Fentes haltères', 'charge'),
  (9, 'Hip thrust', 'charge'),
  (10, 'Rowing barre', 'charge'),
  (11, 'Tirage vertical', 'charge'),
  (12, 'Curl biceps', 'charge'),
  (13, 'Extension triceps à la poulie', 'charge'),
  (14, 'Tractions', 'poids_du_corps'),
  (15, 'Dips', 'poids_du_corps'),
  (16, 'Pompes', 'poids_du_corps'),
  (17, 'Relevés de jambes', 'poids_du_corps'),
  (18, 'Crunchs', 'poids_du_corps');
