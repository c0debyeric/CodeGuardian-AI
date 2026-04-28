"""Pytest fixtures for backend tests."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport

from src.main import create_app


@pytest.fixture
def app():
    """Create test application instance."""
    return create_app()


@pytest.fixture
async def client(app):
    """Create async test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def mock_bedrock_client():
    """Mock Bedrock client for testing."""
    with patch("src.services.bedrock.BedrockClient") as mock:
        instance = mock.return_value
        instance.analyze_code = AsyncMock()
        yield instance


@pytest.fixture
def sample_code():
    """Sample Python code for testing."""
    return '''
def login(username, password):
    query = f"SELECT * FROM users WHERE username='{username}' AND password='{password}'"
    return db.execute(query)
'''


@pytest.fixture
def sample_findings():
    """Sample security findings response."""
    return {
        "findings": [
            {
                "id": "SQL-001",
                "title": "SQL Injection Vulnerability",
                "severity": "CRITICAL",
                "vulnerability_type": "injection",
                "description": "User input is directly interpolated into SQL query without sanitization.",
                "line_start": 2,
                "line_end": 2,
                "recommendation": "Use parameterized queries or an ORM to prevent SQL injection.",
                "cwe_id": "CWE-89",
                "owasp_category": "A03:2021-Injection"
            }
        ],
        "summary": {
            "total": 1,
            "critical": 1,
            "high": 0,
            "medium": 0,
            "low": 0,
            "info": 0
        },
        "metadata": {
            "language_detected": "python",
            "lines_analyzed": 4,
            "scan_time_ms": 100,
            "model_used": "claude-sonnet-4-5"
        }
    }
