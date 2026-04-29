# LLM Gateway - Makefile
# Common commands for development

.PHONY: help install dev-backend dev-ui test lint docker-up docker-down clean

help:
	@echo "LLM Gateway - Available Commands"
	@echo "================================="
	@echo "install          Install backend deps (uv) and admin-ui deps (npm)"
	@echo "dev-backend      Run FastAPI gateway with reload on :8000"
	@echo "dev-ui           Run Next.js admin UI on :3000"
	@echo "test             Run backend pytest suite"
	@echo "test-cov         Run backend tests with coverage"
	@echo "lint             Lint backend (ruff) and admin-ui (next lint)"
	@echo "format           Format backend code (ruff format)"
	@echo "typecheck        mypy on backend, tsc on admin-ui"
	@echo "docker-up        Start full stack (gateway + Redis + Postgres + OTel + UI)"
	@echo "docker-up-d      Same, detached"
	@echo "docker-down      Stop all docker compose services"
	@echo "docker-logs      Tail all service logs"
	@echo "clean            Remove caches and build artifacts"

# ===========================================
# Installation
# ===========================================
install: install-backend install-ui

install-backend:
	cd app/backend && uv sync --all-extras

install-ui:
	cd app/admin-ui && npm install --no-audit --no-fund

# ===========================================
# Development
# ===========================================
dev-backend:
	cd app/backend && uv run uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

dev-ui:
	cd app/admin-ui && GATEWAY_URL=http://localhost:8000 ADMIN_API_KEY=dev-admin-key-change-me npm run dev

# ===========================================
# Testing / quality
# ===========================================
test:
	cd app/backend && uv run pytest -v

test-cov:
	cd app/backend && uv run pytest --cov=src --cov-report=html

lint:
	cd app/backend && uv run ruff check .
	cd app/admin-ui && npm run lint

lint-fix:
	cd app/backend && uv run ruff check --fix .

format:
	cd app/backend && uv run ruff format .

typecheck:
	cd app/backend && uv run mypy src/
	cd app/admin-ui && npm run typecheck

# ===========================================
# Docker
# ===========================================
docker-build:
	docker compose build

docker-up:
	docker compose up --build

docker-up-d:
	docker compose up --build -d

docker-down:
	docker compose down

docker-logs:
	docker compose logs -f

docker-logs-backend:
	docker compose logs -f backend

docker-logs-ui:
	docker compose logs -f admin-ui

# ===========================================
# Cleanup
# ===========================================
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".next" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "node_modules" -exec rm -rf {} + 2>/dev/null || true
