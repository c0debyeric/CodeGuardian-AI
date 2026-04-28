# CodeGuardian AI - Frontend

Streamlit UI for the AI-powered security code reviewer.

## Quick Start

```bash
# Install dependencies
uv sync

# Run Streamlit
uv run streamlit run src/app.py --server.port 8501

# Run linter
uv run ruff check .
```

## Features

- Code input with syntax highlighting
- Language selection (Python, JavaScript, Terraform)
- Severity-colored results display
- Finding details with fix suggestions
