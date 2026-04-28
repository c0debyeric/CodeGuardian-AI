"""Code analyzer service - orchestrates the analysis workflow."""

import uuid

import structlog

from src.api.schemas import Finding, Language, Severity
from src.services.bedrock import BedrockClient

logger = structlog.get_logger()


class CodeAnalyzer:
    """Orchestrates code security analysis using Bedrock."""

    def __init__(self) -> None:
        """Initialize the analyzer with Bedrock client."""
        self.bedrock = BedrockClient()

    def check_bedrock_connection(self) -> bool:
        """Check if Bedrock is accessible."""
        return self.bedrock.check_connection()

    async def analyze(
        self,
        code: str,
        language: str = "auto",
        context: str | None = None,
    ) -> tuple[list[Finding], str]:
        """
        Analyze code for security vulnerabilities.

        Args:
            code: The source code to analyze
            language: Programming language (or 'auto' for detection)
            context: Optional additional context

        Returns:
            Tuple of (list of findings, detected language)
        """
        # Detect language if auto
        detected_language = self._detect_language(code) if language == "auto" else language

        logger.info("Starting analysis", language=detected_language, code_lines=len(code.splitlines()))

        # Call Bedrock for analysis
        try:
            raw_findings = await self.bedrock.analyze_code(
                code=code,
                language=detected_language,
                context=context,
            )
        except Exception as e:
            logger.error("Bedrock analysis failed", error=str(e))
            raise

        # Parse and validate findings
        findings = self._parse_findings(raw_findings)

        return findings, detected_language

    def _detect_language(self, code: str) -> str:
        """
        Simple language detection based on code patterns.

        For MVP, this uses basic heuristics. Could be enhanced with ML later.
        """
        code_lower = code.lower()

        # Terraform detection
        if any(
            pattern in code_lower
            for pattern in ["resource \"", "provider \"", "terraform {", "variable \"", "module \""]
        ):
            return Language.TERRAFORM.value

        # JavaScript/TypeScript detection
        if any(
            pattern in code
            for pattern in [
                "const ",
                "let ",
                "function(",
                "function (",
                "=>",
                "require(",
                "import ",
                "export ",
                "console.log",
            ]
        ):
            return Language.JAVASCRIPT.value

        # Default to Python (most common in security context)
        return Language.PYTHON.value

    def _parse_findings(self, raw_findings: list[dict]) -> list[Finding]:
        """Parse raw findings from Bedrock into Finding objects."""
        findings: list[Finding] = []

        for i, raw in enumerate(raw_findings):
            try:
                finding = Finding(
                    id=raw.get("id", f"f{i + 1}"),
                    severity=Severity(raw.get("severity", "MEDIUM").upper()),
                    line_start=raw.get("line_start", raw.get("line", 1)),
                    line_end=raw.get("line_end", raw.get("line", 1)),
                    vulnerability_type=raw.get("vulnerability_type", "Unknown"),
                    cwe_id=raw.get("cwe_id"),
                    owasp_category=raw.get("owasp_category"),
                    title=raw.get("title", "Security Issue"),
                    description=raw.get("description", ""),
                    recommendation=raw.get("recommendation", "Review and fix this issue"),
                    code_snippet=raw.get("code_snippet"),
                    fix_example=raw.get("fix_example"),
                )
                findings.append(finding)
            except Exception as e:
                logger.warning("Failed to parse finding", index=i, error=str(e), raw=raw)
                continue

        return findings
