"""API route definitions."""

import time

import structlog
from fastapi import APIRouter, HTTPException, status

from src.api.schemas import (
    AnalysisMetadata,
    AnalysisSummary,
    AnalyzeRequest,
    AnalyzeResponse,
    ErrorResponse,
    Finding,
    HealthResponse,
    Severity,
)
from src.core.config import get_settings
from src.services.analyzer import CodeAnalyzer

logger = structlog.get_logger()
router = APIRouter()

# Initialize analyzer (will be properly initialized when Bedrock service is ready)
analyzer: CodeAnalyzer | None = None


def get_analyzer() -> CodeAnalyzer:
    """Get or create the code analyzer instance."""
    global analyzer
    if analyzer is None:
        analyzer = CodeAnalyzer()
    return analyzer


@router.get(
    "/health",
    response_model=HealthResponse,
    tags=["Health"],
    summary="Health check endpoint",
    description="Check if the API is running and Bedrock is accessible.",
)
async def health_check() -> HealthResponse:
    """Health check endpoint."""
    settings = get_settings()

    # Check Bedrock connectivity
    try:
        analyzer_instance = get_analyzer()
        bedrock_connected = analyzer_instance.check_bedrock_connection()
    except Exception as e:
        logger.warning("Bedrock connection check failed", error=str(e))
        bedrock_connected = False

    return HealthResponse(
        status="healthy",
        version=settings.app_version,
        bedrock_connected=bedrock_connected,
    )


@router.post(
    "/analyze",
    response_model=AnalyzeResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
        503: {"model": ErrorResponse, "description": "Bedrock service unavailable"},
    },
    tags=["Analysis"],
    summary="Analyze code for security vulnerabilities",
    description="Submit code for AI-powered security analysis. Returns findings with severity, CWE mappings, and fix suggestions.",
)
async def analyze_code(request: AnalyzeRequest) -> AnalyzeResponse:
    """Analyze code for security vulnerabilities."""
    start_time = time.perf_counter()
    settings = get_settings()

    logger.info(
        "Code analysis requested",
        language=request.language.value,
        code_length=len(request.code),
        has_context=request.context is not None,
    )

    try:
        analyzer_instance = get_analyzer()
        findings, detected_language = await analyzer_instance.analyze(
            code=request.code,
            language=request.language.value,
            context=request.context,
        )
    except ConnectionError as e:
        logger.error("Bedrock connection failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "ServiceUnavailable", "message": "AI service temporarily unavailable"},
        )
    except Exception as e:
        logger.exception("Analysis failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "AnalysisError", "message": "Failed to analyze code"},
        )

    # Calculate scan time
    scan_time_ms = int((time.perf_counter() - start_time) * 1000)

    # Build summary
    summary = AnalysisSummary(
        total=len(findings),
        critical=sum(1 for f in findings if f.severity == Severity.CRITICAL),
        high=sum(1 for f in findings if f.severity == Severity.HIGH),
        medium=sum(1 for f in findings if f.severity == Severity.MEDIUM),
        low=sum(1 for f in findings if f.severity == Severity.LOW),
        info=sum(1 for f in findings if f.severity == Severity.INFO),
    )

    # Build metadata
    metadata = AnalysisMetadata(
        language_detected=detected_language,
        lines_analyzed=len(request.code.splitlines()),
        scan_time_ms=scan_time_ms,
        model_used="claude-sonnet-4-5",
    )

    logger.info(
        "Analysis completed",
        findings_count=len(findings),
        scan_time_ms=scan_time_ms,
        language=detected_language,
    )

    return AnalyzeResponse(
        findings=findings,
        summary=summary,
        metadata=metadata,
    )
