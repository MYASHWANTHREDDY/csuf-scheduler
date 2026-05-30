# Convenience Makefile for local development (requires GNU make)

.PHONY: build up migrate logs smoke down

build:
	@echo "Building backend and migrate images..."
	docker compose build --no-cache

up:
	@echo "Starting web, db and redis in background..."
	docker compose up -d web db redis

migrate:
	@echo "Running containerized migrations (alembic upgrade head)..."
	docker compose run --rm migrate

logs:
	@echo "Tailing web logs... (ctrl-c to exit)"
	docker compose logs -f web

smoke:
	@echo "Running smoke test against http://127.0.0.1:5000"
	python scripts/smoke_test.py

down:
	@echo "Stopping all compose services..."
	docker compose down -v
