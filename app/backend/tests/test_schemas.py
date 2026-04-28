"""Tests for Pydantic schema validation."""

import pytest
from pydantic import ValidationError

from src.api.schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    Finding,
    AnalysisSummary,
    Severity,
    HealthResponse,
    Language,
)


class TestAnalyzeRequest:
    """Tests for AnalyzeRequest schema."""

    def test_valid_request_code_only(self):
        """Test valid request with only code."""
        request = AnalyzeRequest(code="def foo(): pass")
        assert request.code == "def foo(): pass"
        assert request.language == Language.AUTO

    def test_valid_request_with_language(self):
        """Test valid request with code and language."""
        request = AnalyzeRequest(code="def foo(): pass", language=Language.PYTHON)
        assert request.code == "def foo(): pass"
        assert request.language == Language.PYTHON

    def test_empty_code_rejected(self):
        """Test that empty code is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            AnalyzeRequest(code="")
        assert "code" in str(exc_info.value).lower()

    def test_code_too_large_rejected(self):
        """Test that oversized code is rejected."""
        large_code = "x" * (100 * 1000 + 1)  # Over 100KB
        with pytest.raises(ValidationError) as exc_info:
            AnalyzeRequest(code=large_code)
        # Validation should fail


class TestFinding:
    """Tests for Finding schema."""

    def test_valid_finding(self):
        """Test valid finding creation."""
        finding = Finding(
            id="SQL-001",
            title="SQL Injection",
            severity=Severity.CRITICAL,
            vulnerability_type="injection",
            description="Vulnerable to SQL injection",
            line_start=1,
            line_end=1,
            recommendation="Use parameterized queries",
        )
        assert finding.id == "SQL-001"
        assert finding.severity == Severity.CRITICAL

    def test_finding_with_optional_fields(self):
        """Test finding with optional fields populated."""
        finding = Finding(
            id="XSS-001",
            title="XSS Vulnerability",
            severity=Severity.HIGH,
            vulnerability_type="xss",
            description="Cross-site scripting",
            line_start=5,
            line_end=7,
            recommendation="Sanitize output",
            cwe_id="CWE-79",
            owasp_category="A03:2021-Injection",
        )
        assert finding.cwe_id == "CWE-79"
        assert finding.owasp_category == "A03:2021-Injection"

    def test_finding_without_optional_fields(self):
        """Test finding without optional fields."""
        finding = Finding(
            id="TEST-001",
            title="Test Finding",
            severity=Severity.LOW,
            vulnerability_type="test",
            description="Test description",
            line_start=1,
            line_end=1,
            recommendation="Test recommendation",
        )
        assert finding.cwe_id is None
        assert finding.owasp_category is None


class TestSeverity:
    """Tests for Severity enum."""

    def test_all_severity_levels(self):
        """Test all severity levels are defined."""
        assert Severity.CRITICAL == "CRITICAL"
        assert Severity.HIGH == "HIGH"
        assert Severity.MEDIUM == "MEDIUM"
        assert Severity.LOW == "LOW"
        assert Severity.INFO == "INFO"

    def test_invalid_severity_rejected(self):
        """Test invalid severity is rejected."""
        with pytest.raises(ValidationError):
            Finding(
                id="TEST-001",
                title="Test",
                severity="invalid",  # Invalid severity
                vulnerability_type="test",
                description="Test",
                line_start=1,
                line_end=1,
                recommendation="Test",
            )


class TestAnalysisSummary:
    """Tests for AnalysisSummary schema."""

    def test_valid_summary(self):
        """Test valid summary creation."""
        summary = AnalysisSummary(
            total=5,
            critical=1,
            high=2,
            medium=1,
            low=1,
            info=0,
        )
        assert summary.total == 5
        assert summary.critical == 1

    def test_summary_defaults_to_zero(self):
        """Test summary fields default to zero."""
        summary = AnalysisSummary(total=0)
        assert summary.critical == 0
        assert summary.high == 0
        assert summary.medium == 0
        assert summary.low == 0
        assert summary.info == 0


class TestHealthResponse:
    """Tests for HealthResponse schema."""

    def test_valid_health_response(self):
        """Test valid health response."""
        response = HealthResponse(
            status="healthy",
            version="0.1.0",
            bedrock_connected=True,
        )
        assert response.status == "healthy"
        assert response.bedrock_connected is True

    def test_health_response_unhealthy(self):
        """Test health response when unhealthy."""
        response = HealthResponse(
            status="healthy",
            version="0.1.0",
            bedrock_connected=False,
        )
        assert response.bedrock_connected is False
