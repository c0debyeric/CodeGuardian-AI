"""Tests for health endpoint."""

import pytest
from unittest.mock import patch, MagicMock


@pytest.mark.asyncio
async def test_health_endpoint_healthy(client):
    """Test health endpoint returns healthy status."""
    with patch("src.api.routes.get_analyzer") as mock_get_analyzer:
        # Mock successful Bedrock connection
        mock_analyzer = MagicMock()
        mock_analyzer.check_bedrock_connection.return_value = True
        mock_get_analyzer.return_value = mock_analyzer
        
        response = await client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data
        assert data["bedrock_connected"] is True


@pytest.mark.asyncio
async def test_health_endpoint_returns_version(client):
    """Test health endpoint includes version info."""
    with patch("src.api.routes.get_analyzer") as mock_get_analyzer:
        mock_analyzer = MagicMock()
        mock_analyzer.check_bedrock_connection.return_value = True
        mock_get_analyzer.return_value = mock_analyzer
        
        response = await client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["version"] == "0.1.0"


@pytest.mark.asyncio
async def test_health_endpoint_bedrock_disconnected(client):
    """Test health endpoint handles Bedrock connection failure."""
    with patch("src.api.routes.get_analyzer") as mock_get_analyzer:
        # Mock Bedrock connection failure
        mock_analyzer = MagicMock()
        mock_analyzer.check_bedrock_connection.side_effect = Exception("Connection failed")
        mock_get_analyzer.return_value = mock_analyzer
        
        response = await client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["bedrock_connected"] is False
