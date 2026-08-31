# ── KnowDecay Engine — Developer Workflow Commands ────────────────────────────
#
# Usage:
#   make help        — list all available commands
#   make up          — start development stack
#   make test        — run test suite
#   make lint        — check code quality
# ──────────────────────────────────────────────────────────────────────────────

.DEFAULT_GOAL := help
.PHONY: help up down restart rebuild logs shell \
        db db-shell migrate migration db-reset \
        test test-all test-engine lint format \
        build clean production

# ── Development ───────────────────────────────────────────────────────────────

help: ## Show this help message
	@echo ""
	@echo "KnowDecay Engine — Available Commands"
	@echo "══════════════════════════════════════"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'
	@echo ""

up: ## Start development stack (DB + API with hot-reload)
	docker compose up

up-d: ## Start development stack (detached)
	docker compose up -d

down: ## Stop all containers
	docker compose down

restart: ## Restart development stack
	docker compose down
	docker compose up

rebuild: ## Rebuild and restart containers
	docker compose down
	docker compose build
	docker compose up

logs: ## Follow API container logs
	docker compose logs -f api

shell: ## Open a shell inside the API container
	docker compose exec api /bin/bash

# ── Database ──────────────────────────────────────────────────────────────────

db: ## Start database only
	docker compose up db

db-d: ## Start database only (detached)
	docker compose up -d db

db-shell: ## Open psql inside the database container
	docker compose exec db psql -U knowdecay -d knowdecay

migrate: ## Run Alembic migrations via dedicated service
	docker compose --profile tools run --rm migrate

migration: ## Generate a new Alembic migration (usage: make migration MSG="description")
	alembic revision --autogenerate -m "$(MSG)"

db-reset: ## Reset database: drop volume, recreate, and migrate
	@echo "⚠  This will DELETE all database data."
	@read -p "Continue? (y/N) " confirm && [ "$$confirm" = "y" ] || exit 1
	docker compose down -v
	docker compose up -d db
	@echo "Waiting for database..."
	@sleep 5
	docker compose --profile tools run --rm migrate
	@echo "✓ Database reset complete"

# ── Testing ───────────────────────────────────────────────────────────────────

test: ## Run the full test suite (requires PostgreSQL)
	APP_ENV=testing JWT_SECRET_KEY=test-secret-key-minimum-32-characters-long \
		pytest tests/ -v --tb=short

test-engine: ## Run engine-only tests (no database required)
	APP_ENV=testing JWT_SECRET_KEY=test-secret-key-minimum-32-characters-long \
		pytest tests/test_engine/ tests/test_simulation/ -v --tb=short

# ── Code Quality ──────────────────────────────────────────────────────────────

lint: ## Check linting and formatting
	ruff check .
	ruff format --check .

format: ## Auto-fix formatting
	ruff format .
	ruff check --fix .

# ── Docker ────────────────────────────────────────────────────────────────────

build: ## Build Docker image
	docker compose build

production: ## Start production stack (Gunicorn + Uvicorn workers)
	docker compose --profile production up

clean: ## Remove all containers, volumes, and images
	@echo "⚠  This will DELETE all containers, volumes, and built images."
	@read -p "Continue? (y/N) " confirm && [ "$$confirm" = "y" ] || exit 1
	docker compose --profile production --profile test --profile tools down -v --rmi local
	@echo "✓ Clean complete"
