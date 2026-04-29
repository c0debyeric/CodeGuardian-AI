"""OpenAI provider (works for OpenAI itself and any OpenAI-API-compatible
endpoint such as Azure OpenAI, Together, Fireworks, vLLM, llama.cpp server)."""

from __future__ import annotations

import httpx
import structlog

from src.api.schemas import ChatCompletionRequest
from src.core.config import get_settings
from src.providers.base import Provider, ProviderError, ProviderResponse

logger = structlog.get_logger(__name__)


OPENAI_MODELS = [
    "gpt-4o",
    "gpt-4o-mini",
    "gpt-4.1",
    "gpt-4.1-mini",
]


class OpenAIProvider(Provider):
    name = "openai"
    default_model = "gpt-4o-mini"

    def __init__(self) -> None:
        self.settings = get_settings()
        self._client: httpx.AsyncClient | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            if not self.settings.openai_api_key:
                raise ProviderError("openai api key missing", retryable=False)
            self._client = httpx.AsyncClient(
                base_url=self.settings.openai_base_url,
                headers={"Authorization": f"Bearer {self.settings.openai_api_key}"},
                timeout=self.settings.request_timeout_seconds,
            )
        return self._client

    def supports_model(self, model_id: str) -> bool:
        return model_id in OPENAI_MODELS or model_id.startswith(("gpt-", "o1-", "o3-"))

    def list_models(self) -> list[str]:
        return list(OPENAI_MODELS)

    async def chat(
        self, request: ChatCompletionRequest, *, upstream_model: str
    ) -> ProviderResponse:
        body = self._build_body(request, upstream_model)
        try:
            response = await self.client.post("/chat/completions", json=body)
        except httpx.RequestError as e:
            raise ProviderError(f"openai network: {e}", retryable=True) from e

        if response.status_code >= 500 or response.status_code in (408, 429):
            raise ProviderError(
                f"openai {response.status_code}: {response.text[:200]}",
                retryable=True,
                status_code=response.status_code,
            )
        if response.status_code >= 400:
            raise ProviderError(
                f"openai {response.status_code}: {response.text[:200]}",
                retryable=False,
                status_code=response.status_code,
            )

        payload = response.json()
        return self._parse_response(payload, upstream_model)

    def _build_body(self, request: ChatCompletionRequest, upstream_model: str) -> dict:
        body: dict = {
            "model": upstream_model,
            "messages": [m.model_dump(exclude_none=True) for m in request.messages],
            "stream": False,
        }
        if request.temperature is not None:
            body["temperature"] = request.temperature
        if request.max_tokens is not None:
            body["max_tokens"] = request.max_tokens
        if request.top_p is not None:
            body["top_p"] = request.top_p
        if request.stop:
            body["stop"] = request.stop
        if request.user:
            body["user"] = request.user
        return body

    def _parse_response(self, payload: dict, upstream_model: str) -> ProviderResponse:
        choices = payload.get("choices") or []
        text = ""
        finish = "stop"
        if choices:
            msg = choices[0].get("message") or {}
            text = msg.get("content") or ""
            finish = choices[0].get("finish_reason") or "stop"
        usage = payload.get("usage") or {}
        return ProviderResponse(
            content=text,
            model=payload.get("model") or upstream_model,
            prompt_tokens=int(usage.get("prompt_tokens", 0)),
            completion_tokens=int(usage.get("completion_tokens", 0)),
            finish_reason=finish,
            raw=payload,
        )

    async def health(self) -> bool:
        return bool(self.settings.openai_api_key)
