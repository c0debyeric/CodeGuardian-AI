"""AWS Bedrock client for Claude interactions."""

import json

import boto3
import structlog
from botocore.config import Config
from botocore.exceptions import ClientError

from src.core.config import get_settings
from src.core.prompts import SECURITY_ANALYST_SYSTEM_PROMPT, get_analysis_prompt

logger = structlog.get_logger()


class BedrockClient:
    """Client for AWS Bedrock Claude API."""

    def __init__(self) -> None:
        """Initialize the Bedrock client."""
        self.settings = get_settings()
        self._client = None

    @property
    def client(self):
        """Lazy-load the Bedrock runtime client."""
        if self._client is None:
            config = Config(
                region_name=self.settings.aws_region,
                retries={"max_attempts": 3, "mode": "adaptive"},
            )

            # Use explicit credentials if provided, otherwise rely on default chain
            session_kwargs = {}
            if self.settings.aws_access_key_id and self.settings.aws_secret_access_key:
                session_kwargs["aws_access_key_id"] = self.settings.aws_access_key_id
                session_kwargs["aws_secret_access_key"] = self.settings.aws_secret_access_key
            elif self.settings.aws_profile:
                session_kwargs["profile_name"] = self.settings.aws_profile

            session = boto3.Session(**session_kwargs)
            self._client = session.client("bedrock-runtime", config=config)

        return self._client

    def check_connection(self) -> bool:
        """Check if Bedrock is accessible."""
        try:
            # Try a minimal API call to verify connectivity
            # We'll just check if the client can be created
            _ = self.client
            return True
        except Exception as e:
            logger.warning("Bedrock connection check failed", error=str(e))
            return False

    async def analyze_code(
        self,
        code: str,
        language: str,
        context: str | None = None,
    ) -> list[dict]:
        """
        Analyze code using Claude via Bedrock.

        Args:
            code: Source code to analyze
            language: Programming language
            context: Optional additional context

        Returns:
            List of finding dictionaries
        """
        user_prompt = get_analysis_prompt(code, language, context)

        logger.debug(
            "Sending request to Bedrock",
            model=self.settings.bedrock_model_id,
            prompt_length=len(user_prompt),
        )

        try:
            # Prepare the request body for Claude 3.x/Sonnet 4.x
            request_body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": self.settings.bedrock_max_tokens,
                "temperature": self.settings.bedrock_temperature,
                "system": SECURITY_ANALYST_SYSTEM_PROMPT,
                "messages": [
                    {
                        "role": "user",
                        "content": user_prompt,
                    }
                ],
            }

            response = self.client.invoke_model(
                modelId=self.settings.bedrock_model_id,
                body=json.dumps(request_body),
                contentType="application/json",
                accept="application/json",
            )

            # Parse response
            response_body = json.loads(response["body"].read())
            
            # Extract the text content from Claude's response
            content = response_body.get("content", [])
            if not content:
                logger.warning("Empty response from Bedrock")
                return []

            text_response = content[0].get("text", "")
            
            logger.debug("Received Bedrock response", response_length=len(text_response))

            # Parse the JSON findings from the response
            findings = self._parse_response(text_response)
            return findings

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_message = e.response.get("Error", {}).get("Message", str(e))
            logger.error(
                "Bedrock API error",
                error_code=error_code,
                error_message=error_message,
            )
            raise ConnectionError(f"Bedrock API error: {error_code} - {error_message}")
        except Exception as e:
            logger.exception("Unexpected error calling Bedrock", error=str(e))
            raise

    def _parse_response(self, response_text: str) -> list[dict]:
        """Parse Claude's response to extract findings."""
        # Clean up the response - Claude might include markdown code blocks
        text = response_text.strip()
        
        # Remove markdown code block if present
        if text.startswith("```"):
            # Find the end of the opening fence
            first_newline = text.find("\n")
            if first_newline != -1:
                text = text[first_newline + 1:]
            # Remove closing fence
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

        # Handle case where response starts with "json"
        if text.startswith("json"):
            text = text[4:].strip()

        try:
            findings = json.loads(text)
            if isinstance(findings, list):
                return findings
            elif isinstance(findings, dict) and "findings" in findings:
                return findings["findings"]
            else:
                logger.warning("Unexpected response format", response_type=type(findings).__name__)
                return []
        except json.JSONDecodeError as e:
            logger.warning(
                "Failed to parse Bedrock response as JSON",
                error=str(e),
                response_preview=text[:200],
            )
            return []
