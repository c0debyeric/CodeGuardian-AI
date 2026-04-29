"""Provider registry + circuit breaker.

Holds all enabled provider instances and the per-provider circuit state.
The router asks the registry for "providers that can serve model X" and the
registry filters out providers whose circuit is currently open.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Literal

import structlog

from src.core.config import get_settings
from src.providers.base import Provider

logger = structlog.get_logger(__name__)

CircuitState = Literal["closed", "open", "half_open"]


@dataclass
class CircuitBreaker:
    failure_threshold: int = 5
    recovery_seconds: int = 30
    failures: int = 0
    state: CircuitState = "closed"
    opened_at: float = 0.0

    def record_success(self) -> None:
        self.failures = 0
        self.state = "closed"

    def record_failure(self) -> None:
        self.failures += 1
        if self.failures >= self.failure_threshold:
            self.state = "open"
            self.opened_at = time.monotonic()

    def allow(self) -> bool:
        if self.state == "closed":
            return True
        if self.state == "open":
            if time.monotonic() - self.opened_at >= self.recovery_seconds:
                self.state = "half_open"
                return True
            return False
        # half_open: allow a single trial
        return True


@dataclass
class ProviderEntry:
    provider: Provider
    breaker: CircuitBreaker = field(default_factory=CircuitBreaker)


class ProviderRegistry:
    def __init__(self) -> None:
        self._entries: dict[str, ProviderEntry] = {}

    def register(self, provider: Provider) -> None:
        s = get_settings()
        self._entries[provider.name] = ProviderEntry(
            provider=provider,
            breaker=CircuitBreaker(
                failure_threshold=s.circuit_breaker_failure_threshold,
                recovery_seconds=s.circuit_breaker_recovery_seconds,
            ),
        )
        logger.info("provider.registered", provider=provider.name)

    def get(self, name: str) -> ProviderEntry | None:
        return self._entries.get(name)

    def all(self) -> list[ProviderEntry]:
        return list(self._entries.values())

    def for_model(self, model_id: str, *, only_available: bool = True) -> list[ProviderEntry]:
        out: list[ProviderEntry] = []
        for entry in self._entries.values():
            if not entry.provider.supports_model(model_id):
                continue
            if only_available and not entry.breaker.allow():
                continue
            out.append(entry)
        return out

    def list_all_models(self) -> list[str]:
        seen: set[str] = set()
        models: list[str] = []
        for entry in self._entries.values():
            for m in entry.provider.list_models():
                if m not in seen:
                    seen.add(m)
                    models.append(m)
        return models


_registry: ProviderRegistry | None = None


def build_registry() -> ProviderRegistry:
    """Construct the registry from settings. Called once at startup."""
    from src.providers.bedrock import BedrockProvider
    from src.providers.openai import OpenAIProvider

    settings = get_settings()
    reg = ProviderRegistry()
    if settings.bedrock_enabled:
        reg.register(BedrockProvider())
    if settings.openai_enabled and settings.openai_api_key:
        reg.register(OpenAIProvider())
    if not reg.all():
        logger.warning("registry.empty no providers enabled; gateway will fail requests")
    return reg


def get_registry() -> ProviderRegistry:
    global _registry
    if _registry is None:
        _registry = build_registry()
    return _registry


def reset_registry() -> None:
    """Test helper."""
    global _registry
    _registry = None
