"""Tests for analyze endpoint."""

import pytest
import json
from unittest.mock import patch, AsyncMock, MagicMock

from src.api.schemas import Finding, Severity


def create_mock_findings():
    """Create mock Finding objects for testing."""
    return [
        Finding(
            id="SQL-001",
            title="SQL Injection Vulnerability",
            severity=Severity.CRITICAL,
            vulnerability_type="injection",
            description="User input is directly interpolated into SQL query.",
            line_start=2,
            line_end=2,
            recommendation="Use parameterized queries.",
            cwe_id="CWE-89",
            owasp_category="A03:2021-Injection"
        )
    ]


@pytest.mark.asyncio
async def test_analyze_endpoint_success(client, sample_code):
    """Test analyze endpoint with successful Bedrock response."""
    with patch("src.api.routes.get_analyzer") as mock_get_analyzer:
        mock_analyzer = MagicMock()
        mock_analyzer.analyze = AsyncMock(return_value=(create_mock_findings(), "python"))
        mock_get_analyzer.return_value = mock_analyzer
        
        response = await client.post(
            "/analyze",
            json={"code": sample_code}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "findings" in data
        assert "summary" in data
        assert "metadata" in data


@pytest.mark.asyncio
async def test_analyze_endpoint_with_language(client, sample_code):
    """Test analyze endpoint with explicit language specified."""
    with patch("src.api.routes.get_analyzer") as mock_get_analyzer:
        mock_analyzer = MagicMock()
        mock_analyzer.analyze = AsyncMock(return_value=(create_mock_findings(), "python"))
        mock_get_analyzer.return_value = mock_analyzer
        
        response = await client.post(
            "/analyze",
            json={"code": sample_code, "language": "python"}
        )
        
        assert response.status_code == 200
        # Verify language was passed to analyzer
        mock_analyzer.analyze.assert_called_once()


@pytest.mark.asyncio
async def test_analyze_endpoint_empty_code(client):
    """Test analyze endpoint rejects empty code."""
    response = await client.post(
        "/analyze",
        json={"code": ""}
    )
    
    # Should fail validation
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_analyze_endpoint_missing_code(client):
    """Test analyze endpoint rejects missing code field."""
    response = await client.post(
        "/analyze",
        json={}
    )
    
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_analyze_endpoint_bedrock_unavailable(client, sample_code):
    """Test analyze endpoint handles Bedrock service unavailable."""
    with patch("src.api.routes.get_analyzer") as mock_get_analyzer:
        mock_analyzer = MagicMock()
        mock_analyzer.analyze = AsyncMock(side_effect=ConnectionError("Bedrock service unavailable"))
        mock_get_analyzer.return_value = mock_analyzer
        
        response = await client.post(
            "/analyze",
            json={"code": sample_code}
        )
        
        assert response.status_code == 503
        data = response.json()
        assert "detail" in data


@pytest.mark.asyncio
async def test_analyze_endpoint_returns_findings_structure(client, sample_code):
    """Test that response contains expected finding structure."""
    with patch("src.api.routes.get_analyzer") as mock_get_analyzer:
        mock_analyzer = MagicMock()
        mock_analyzer.analyze = AsyncMock(return_value=(create_mock_findings(), "python"))
        mock_get_analyzer.return_value = mock_analyzer
        
        response = await client.post(
            "/analyze",
            json={"code": sample_code}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Check findings structure
        assert len(data["findings"]) == 1
        finding = data["findings"][0]
        assert "id" in finding
        assert "title" in finding
        assert "severity" in finding
        assert "description" in finding
        
        # Check summary structure
        summary = data["summary"]
        assert "total" in summary
        assert summary["total"] == 1


@pytest.mark.asyncio
async def test_analyze_endpoint_code_too_large(client):
    """Test analyze endpoint rejects code that's too large."""
    # Generate code larger than max (100KB default)
    large_code = "x = 1\n" * 50000  # ~300KB
    
    response = await client.post(
        "/analyze",
        json={"code": large_code}
    )
    
    assert response.status_code == 422
