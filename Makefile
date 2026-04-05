# Makefile — Raccourcis de commandes pour GymTrack


.PHONY: up down restart test logs build clean help


up:
	docker compose up -d --build

down:
	docker compose down

restart-app:
	docker compose restart app

build:
	docker compose build

test:
	docker compose exec app pytest -v

logs:
	docker compose logs -f

logs-app:
	docker compose logs -f app

clean:
	docker compose down -v