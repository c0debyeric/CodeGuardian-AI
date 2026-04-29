"""Provider abstraction.

All upstream LLM providers (Bedrock, OpenAI, Anthropic direct, local vLLM)
implement the same `Provider` interface. The router selects a provider per
request and the rest of the system never cares which one ran.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field

from src.api.schemas import ChatCompletionRequest


@dataclass
class ProviderResponse:
    """Normalized provider response (OpenAI-shaped)."""

    content: str
    model: str  # the upstream model id actually invoked
    prompt_tokens: int = 0
    completion_tokens: int = 0
    finish_reason: str = "stop"
    raw: dict | None = None
    extra: dict = field(default_factory=dict)

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


class ProviderError(Exception):
    """Raised by providers on upstream failure. Routing layer decides retry/fallback."""

    def __init__(self, message: str, *, retryable: bool = True, status_code: int | None = None):
        super().__init__(message)
        self.retryable = retryable
        self.status_code = status_code


class Provider(abc.ABC):
    """Interface every upstream provider must implement."""

    name: str  # unique short identifier, e.g. "bedrock", "openai"

    @abc.abstractmethod
    def supports_model(self, model_id: str) -> bool:
        """Return True if this provider can serve the given model id."""

    @abc.abstractmethod
    def list_models(self) -> list[str]:
        """Return concrete model ids this provider exposes."""

    @abc.abstractmethod
    async def chat(
        self, request: ChatCompletionRequest, *, upstream_model: str
    ) -> ProviderResponse:
        """Execute a chat completion against the upstream provider.

        `upstream_model` is the provider-specific model id resolved by the router
        (the request's `model` field may be an alias like "auto").
        """

    async def health(self) -> bool:
        """Lightweight health check. Override for active probing."""
        return True
