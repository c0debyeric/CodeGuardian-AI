"""Pydantic schemas for API request/response models."""

from enum import Enum

from pydantic import BaseModel, Field


class Language(str, Enum):
    """Supported programming languages for code analysis."""

    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TERRAFORM = "terraform"
    AUTO = "auto"


class Severity(str, Enum):
    """Severity levels for security findings."""

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class AnalyzeRequest(BaseModel):
    """Request schema for code analysis endpoint."""

    code: str = Field(..., min_length=1, max_length=100000, description="Code to analyze")
    language: Language = Field(
        default=Language.AUTO, description="Programming language (auto-detected if not specified)"
    )
    context: str | None = Field(
        default=None, max_length=1000, description="Additional context for analysis"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "code": 'password = "admin123"\nquery = f"SELECT * FROM users WHERE id = {user_id}"',
                    "language": "python",
                    "context": "This is a Flask web application",
                }
            ]
        }
    }


class Finding(BaseModel):
    """A single security finding from code analysis."""

    id: str = Field(..., description="Unique identifier for this finding")
    severity: Severity = Field(..., description="Severity level")
    line_start: int = Field(..., ge=1, description="Starting line number")
    line_end: int = Field(..., ge=1, description="Ending line number")
    vulnerability_type: str = Field(..., description="Type of vulnerability")
    cwe_id: str | None = Field(default=None, description="CWE identifier (e.g., CWE-89)")
    owasp_category: str | None = Field(
        default=None, description="OWASP category (e.g., A03:2021-Injection)"
    )
    title: str = Field(..., description="Short title of the finding")
    description: str = Field(..., description="Detailed description of the issue")
    recommendation: str = Field(..., description="How to fix the issue")
    code_snippet: str | None = Field(default=None, description="The vulnerable code snippet")
    fix_example: str | None = Field(default=None, description="Example of fixed code")


class AnalysisSummary(BaseModel):
    """Summary statistics for the analysis."""

    total: int = Field(..., ge=0, description="Total number of findings")
    critical: int = Field(default=0, ge=0, description="Number of critical findings")
    high: int = Field(default=0, ge=0, description="Number of high findings")
    medium: int = Field(default=0, ge=0, description="Number of medium findings")
    low: int = Field(default=0, ge=0, description="Number of low findings")
    info: int = Field(default=0, ge=0, description="Number of info findings")


class AnalysisMetadata(BaseModel):
    """Metadata about the analysis."""

    language_detected: str = Field(..., description="Detected or specified language")
    lines_analyzed: int = Field(..., ge=0, description="Number of lines analyzed")
    scan_time_ms: int = Field(..., ge=0, description="Time taken for analysis in milliseconds")
    model_used: str = Field(..., description="AI model used for analysis")


class AnalyzeResponse(BaseModel):
    """Response schema for code analysis endpoint."""

    findings: list[Finding] = Field(default_factory=list, description="List of security findings")
    summary: AnalysisSummary = Field(..., description="Summary of findings")
    metadata: AnalysisMetadata = Field(..., description="Analysis metadata")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "findings": [
                        {
                            "id": "f1",
                            "severity": "HIGH",
                            "line_start": 1,
                            "line_end": 1,
                            "vulnerability_type": "Hardcoded Credentials",
                            "cwe_id": "CWE-798",
                            "owasp_category": "A07:2021-Identification and Authentication Failures",
                            "title": "Hardcoded password detected",
                            "description": "Password is hardcoded in source code",
                            "recommendation": "Use environment variables or a secrets manager",
                            "code_snippet": 'password = "admin123"',
                            "fix_example": 'password = os.environ.get("DB_PASSWORD")',
                        }
                    ],
                    "summary": {
                        "total": 1,
                        "critical": 0,
                        "high": 1,
                        "medium": 0,
                        "low": 0,
                        "info": 0,
                    },
                    "metadata": {
                        "language_detected": "python",
                        "lines_analyzed": 2,
                        "scan_time_ms": 1234,
                        "model_used": "claude-sonnet-4-5",
                    },
                }
            ]
        }
    }


class HealthResponse(BaseModel):
    """Response schema for health check endpoint."""

    status: str = Field(..., description="Health status")
    version: str = Field(..., description="API version")
    bedrock_connected: bool = Field(..., description="Whether Bedrock is accessible")


class ErrorResponse(BaseModel):
    """Response schema for error responses."""

    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    details: dict | None = Field(default=None, description="Additional error details")
