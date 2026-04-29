"""Pytest fixtures for the LLM gateway."""

from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

import src.providers.registry as registry_module
import src.usage.db as db_module
from src.api.schemas import ChatCompletionRequest, ChatMessage
from src.providers.base import Provider, ProviderError, ProviderResponse
from src.providers.registry import ProviderRegistry, reset_registry


class FakeProvider(Provider):
    """Test double: scriptable success/failure for a list of supported models."""

    def __init__(
        self,
        name: str,
        models: list[str],
        *,
        default_model: str | None = None,
        responses: list[ProviderResponse | Exception] | None = None,
    ):
        self.name = name
        self._models = models
        self.default_model = default_model or models[0]
        self._responses: list[ProviderResponse | Exception] = list(responses or [])
        self.calls: list[tuple[str, ChatCompletionRequest]] = []

    def supports_model(self, model_id: str) -> bool:
        return model_id in self._models

    def list_models(self) -> list[str]:
        return list(self._models)

    async def chat(
        self, request: ChatCompletionRequest, *, upstream_model: str
    ) -> ProviderResponse:
        self.calls.append((upstream_model, request))
        if not self._responses:
            return ProviderResponse(
                content=f"echo from {self.name}:{upstream_model}",
                model=upstream_model,
                prompt_tokens=10,
                completion_tokens=5,
            )
        nxt = self._responses.pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        return nxt


@pytest.fixture(autouse=True)
def _reset_registry():
    reset_registry()
    yield
    reset_registry()


@pytest_asyncio.fixture(autouse=True)
async def _fresh_db():
    """Each test gets a fresh in-memory SQLite DB."""
    await db_module.reset_db()
    await db_module.init_db()
    yield
    await db_module.reset_db()


@pytest.fixture
def make_registry():
    def _build(*providers: Provider) -> ProviderRegistry:
        reg = ProviderRegistry()
        for p in providers:
            reg.register(p)
        # Inject as the global registry so route() / API uses it
        registry_module._registry = reg
        return reg

    return _build


@pytest.fixture
def app():
    from src.main import create_app

    return create_app()


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def sample_request() -> ChatCompletionRequest:
    return ChatCompletionRequest(
        model="auto",
        messages=[ChatMessage(role="user", content="hello")],
    )


__all__ = ["FakeProvider", "ProviderError"]
