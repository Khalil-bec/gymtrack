CREATE TABLE IF NOT EXISTS athletes (
  id         INT AUTO_INCREMENT PRIMARY KEY,
  nom        VARCHAR(100) NOT NULL,
  email      VARCHAR(150) UNIQUE NOT NULL,
  poids_kg   DECIMAL(5,2),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
  FOREIGN KEY (seance_id) REFERENCES seances(id)
);

CREATE TABLE IF NOT EXISTS series (
  id             INT AUTO_INCREMENT PRIMARY KEY,
  exercice_id    INT NOT NULL,
  numero_serie   INT NOT NULL,
  poids_kg       DECIMAL(5,2),
  repetitions    INT NOT NULL,
  repos_sec      INT DEFAULT 90,
  FOREIGN KEY (exercice_id) REFERENCES exercice_logs(id)
);

-- Données de test
INSERT INTO athletes (nom, email, poids_kg) VALUES
  ('Khalil', 'khalil@gymtrack.com', 80.5);

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