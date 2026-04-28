# CodeGuardian AI - Makefile
# Common commands for development

.PHONY: help install dev-backend dev-frontend test lint docker-up docker-down clean

# Default target
help:
	@echo "CodeGuardian AI - Available Commands"
	@echo "====================================="
	@echo "install          Install all dependencies"
	@echo "dev-backend      Run backend in development mode"
	@echo "dev-frontend     Run frontend in development mode"
	@echo "dev              Run both backend and frontend (requires 2 terminals)"
	@echo "test             Run all tests"
	@echo "lint             Run linters on all code"
	@echo "format           Format all code"
	@echo "docker-build     Build Docker images"
	@echo "docker-up        Start all services with Docker Compose"
	@echo "docker-down      Stop all Docker services"
	@echo "clean            Remove build artifacts and caches"

# ===========================================
# Installation
# ===========================================
install:
	cd app/backend && uv sync --all-extras
	cd app/frontend && uv sync --all-extras

install-backend:
	cd app/backend && uv sync --all-extras

install-frontend:
	cd app/frontend && uv sync --all-extras

# ===========================================
# Development
# ===========================================
dev-backend:
	cd app/backend && uv run uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

dev-frontend:
	cd app/frontend && uv run streamlit run src/app.py --server.port 8501

# ===========================================
# Testing
# ===========================================
test:
	cd app/backend && uv run pytest -v

test-cov:
	cd app/backend && uv run pytest --cov=src --cov-report=html

# ===========================================
# Linting & Formatting
# ===========================================
lint:
	cd app/backend && uv run ruff check .
	cd app/frontend && uv run ruff check .

lint-fix:
	cd app/backend && uv run ruff check --fix .
	cd app/frontend && uv run ruff check --fix .

format:
	cd app/backend && uv run ruff format .
	cd app/frontend && uv run ruff format .

typecheck:
	cd app/backend && uv run mypy src/

# ===========================================
# Docker
# ===========================================
docker-build:
	docker-compose build

docker-up:
	docker-compose up --build

docker-up-d:
	docker-compose up --build -d

docker-down:
	docker-compose down

docker-logs:
	docker-compose logs -f

docker-logs-backend:
	docker-compose logs -f backend

docker-logs-frontend:
	docker-compose logs -f frontend

# ===========================================
# Cleanup
# ===========================================
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
