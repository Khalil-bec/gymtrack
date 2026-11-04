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

CREATE TABLE IF NOT EXISTS exercice_logs (
  id         INT AUTO_INCREMENT PRIMARY KEY,
  seance_id  INT NOT NULL,
  nom        VARCHAR(100) NOT NULL,
  ordre      INT DEFAULT 1,
  -- Supprimer une séance supprime ses exercices notés (et, en cascade, leurs séries)
  FOREIGN KEY (seance_id) REFERENCES seances(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS series (
  id             INT AUTO_INCREMENT PRIMARY KEY,
  exercice_id    INT NOT NULL,
  numero_serie   INT NOT NULL,
  poids_kg       DECIMAL(5,2),
  repetitions    INT NOT NULL,
  repos_sec      INT DEFAULT 90,
  FOREIGN KEY (exercice_id) REFERENCES exercice_logs(id) ON DELETE CASCADE
);

-- Données de test
INSERT INTO athletes (nom, email) VALUES
  ('Khalil', 'khalil@gymtrack.com');

INSERT INTO pesees (athlete_id, date_pesee, poids_kg) VALUES
  (1, '2026-03-22', 80.5);

INSERT INTO exercices (nom, type) VALUES
  ('Développé couché', 'charge'),
  ('Développé incliné haltères', 'charge'),
  ('Développé militaire', 'charge'),
  ('Élévations latérales', 'charge'),
  ('Squat', 'charge'),
  ('Soulevé de terre', 'charge'),
  ('Presse à cuisses', 'charge'),
  ('Fentes haltères', 'charge'),
  ('Hip thrust', 'charge'),
  ('Rowing barre', 'charge'),
  ('Tirage vertical', 'charge'),
  ('Curl biceps', 'charge'),
  ('Extension triceps à la poulie', 'charge'),
  ('Tractions', 'poids_du_corps'),
  ('Dips', 'poids_du_corps'),
  ('Pompes', 'poids_du_corps'),
  ('Relevés de jambes', 'poids_du_corps'),
  ('Crunchs', 'poids_du_corps');

INSERT INTO seances (athlete_id, titre, date_seance, duree_min) VALUES
  (1, 'Push Day — Poitrine/Épaules/Triceps', '2026-03-22', 75),
  (1, 'Pull Day — Dos/Biceps', '2026-03-20', 65);

INSERT INTO exercice_logs (seance_id, nom, ordre) VALUES
  (1, 'Développé couché', 1),
  (1, 'Développé militaire', 2),
  (2, 'Tractions', 1),
  (2, 'Rowing barre', 2);

INSERT INTO series (exercice_id, numero_serie, poids_kg, repetitions) VALUES
  (1, 1, 80, 8), (1, 2, 80, 7), (1, 3, 75, 8),
  (2, 1, 50, 10), (2, 2, 50, 9),
  (3, 1, 0, 8), (3, 2, 0, 7),
  (4, 1, 60, 10), (4, 2, 60, 9);