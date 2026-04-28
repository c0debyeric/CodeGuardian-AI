# CodeGuardian AI - Backend

FastAPI backend for the AI-powered security code reviewer.

## Quick Start

```bash
# Install dependencies
uv sync

# Run development server
uv run uvicorn src.main:app --reload --port 8000

# Run tests
uv run pytest

# Run linter
uv run ruff check .

# Run type checker
uv run mypy src/
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| POST | `/analyze` | Analyze code for security issues |

## Environment Variables

See `.env.example` in the project root for required configuration.
