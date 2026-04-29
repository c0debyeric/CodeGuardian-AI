"""AWS Bedrock provider (Anthropic Claude family)."""

from __future__ import annotations

import asyncio
import json

import boto3
import structlog
from botocore.config import Config
from botocore.exceptions import ClientError

from src.api.schemas import ChatCompletionRequest
from src.core.config import get_settings
from src.providers.base import Provider, ProviderError, ProviderResponse

logger = structlog.get_logger(__name__)


# Concrete Bedrock model ids this provider can serve. The router uses these
# (plus the `supports_model` check) to route concrete model requests.
BEDROCK_MODELS = [
    "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
    "anthropic.claude-sonnet-4-5-20250929-v1:0",
    "anthropic.claude-haiku-4-5",
]


class BedrockProvider(Provider):
    name = "bedrock"

    # A safe default if caller passes a generic alias. The router normally
    # resolves the alias before invoking the provider.
    default_model = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"

    def __init__(self) -> None:
        self.settings = get_settings()
        self._client = None

    @property
    def client(self):
        if self._client is None:
            cfg = Config(
                region_name=self.settings.aws_region,
                retries={"max_attempts": 3, "mode": "adaptive"},
                read_timeout=self.settings.request_timeout_seconds,
            )
            session_kwargs: dict = {}
            if self.settings.aws_access_key_id and self.settings.aws_secret_access_key:
                session_kwargs["aws_access_key_id"] = self.settings.aws_access_key_id
                session_kwargs["aws_secret_access_key"] = self.settings.aws_secret_access_key
            elif self.settings.aws_profile:
                session_kwargs["profile_name"] = self.settings.aws_profile
            session = boto3.Session(**session_kwargs)
            self._client = session.client("bedrock-runtime", config=cfg)
        return self._client

    def supports_model(self, model_id: str) -> bool:
        return model_id in BEDROCK_MODELS or model_id.startswith(("anthropic.", "us.anthropic."))

    def list_models(self) -> list[str]:
        return list(BEDROCK_MODELS)

    async def chat(
        self, request: ChatCompletionRequest, *, upstream_model: str
    ) -> ProviderResponse:
        body = self._build_request_body(request)
        loop = asyncio.get_running_loop()
        try:
            response = await loop.run_in_executor(
                None,
                lambda: self.client.invoke_model(
                    modelId=upstream_model,
                    body=json.dumps(body),
                    contentType="application/json",
                    accept="application/json",
                ),
            )
            payload = json.loads(response["body"].read())
            return self._parse_response(payload, upstream_model)
        except ClientError as e:
            err = e.response.get("Error", {})
            code = err.get("Code", "Unknown")
            msg = err.get("Message", str(e))
            # Throttling / model-not-ready are retryable; auth/validation are not
            retryable = code in {
                "ThrottlingException",
                "ServiceUnavailableException",
                "ModelNotReadyException",
                "ModelTimeoutException",
                "InternalServerException",
            }
            logger.warning(
                "bedrock.error", code=code, retryable=retryable, model=upstream_model
            )
            raise ProviderError(f"bedrock {code}: {msg}", retryable=retryable) from e
        except Exception as e:
            logger.exception("bedrock.unexpected", model=upstream_model)
            raise ProviderError(f"bedrock unexpected: {e}", retryable=True) from e

    def _build_request_body(self, request: ChatCompletionRequest) -> dict:
        """Translate OpenAI-format messages into Anthropic Messages API format."""
        system_parts: list[str] = []
        messages: list[dict] = []
        for m in request.messages:
            content = m.content if isinstance(m.content, str) else json.dumps(m.content)
            if m.role == "system":
                system_parts.append(content)
            elif m.role in {"user", "assistant"}:
                messages.append({"role": m.role, "content": content})
            # Tool messages: simplified mapping for Phase 1
            elif m.role == "tool":
                messages.append({"role": "user", "content": content})

        body: dict = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": request.max_tokens or 1024,
            "messages": messages,
        }
        if system_parts:
            body["system"] = "\n\n".join(system_parts)
        if request.temperature is not None:
            body["temperature"] = request.temperature
        if request.top_p is not None:
            body["top_p"] = request.top_p
        if request.stop:
            body["stop_sequences"] = (
                [request.stop] if isinstance(request.stop, str) else list(request.stop)
            )
        return body

    def _parse_response(self, payload: dict, upstream_model: str) -> ProviderResponse:
        content_blocks = payload.get("content") or []
        text = "".join(b.get("text", "") for b in content_blocks if b.get("type") == "text")
        usage = payload.get("usage") or {}
        return ProviderResponse(
            content=text,
            model=upstream_model,
            prompt_tokens=int(usage.get("input_tokens", 0)),
            completion_tokens=int(usage.get("output_tokens", 0)),
            finish_reason=payload.get("stop_reason") or "stop",
            raw=payload,
        )

    async def health(self) -> bool:
        try:
            _ = self.client
            return True
        except Exception:
            return False
