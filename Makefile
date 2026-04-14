.PHONY: up down logs migrate seed test-api test-worker shell-api shell-worker rebuild

up:
	docker compose up --build -d
	@echo "Stack started. API: http://localhost:3505/api/docs  Web: http://localhost:3506"

down:
	docker compose down

logs:
	docker compose logs -f

migrate:
	docker compose exec api alembic upgrade head

seed:
	docker compose exec api python scripts/seed.py

test-api:
	docker compose exec api python -m pytest tests/ -v

test-worker:
	docker compose exec worker python -m pytest tests/ -v

shell-api:
	docker compose exec api bash

shell-worker:
	docker compose exec worker bash

rebuild:
	docker compose down && docker compose up --build -d
