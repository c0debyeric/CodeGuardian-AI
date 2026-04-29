"""Tests for HTTP API endpoints."""

from __future__ import annotations

import pytest

from src.providers.base import ProviderError
from tests.conftest import FakeProvider


@pytest.mark.asyncio
async def test_health_returns_provider_states(make_registry, client):
    make_registry(FakeProvider("alpha", ["m1"]))
    r = await client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "healthy"
    assert any(p["name"] == "alpha" for p in body["providers"])


@pytest.mark.asyncio
async def test_list_models_includes_aliases(make_registry, client):
    make_registry(FakeProvider("alpha", ["m1", "m2"]))
    r = await client.get("/v1/models")
    assert r.status_code == 200
    ids = {m["id"] for m in r.json()["data"]}
    assert {"m1", "m2", "auto", "cheapest", "fastest"}.issubset(ids)


@pytest.mark.asyncio
async def test_chat_completions_returns_openai_shape(make_registry, client):
    make_registry(FakeProvider("alpha", ["m1"]))
    r = await client.post(
        "/v1/chat/completions",
        json={"model": "m1", "messages": [{"role": "user", "content": "hi"}]},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["object"] == "chat.completion"
    assert body["choices"][0]["message"]["role"] == "assistant"
    assert "gateway" in body
    assert body["gateway"]["provider"] == "alpha"


@pytest.mark.asyncio
async def test_chat_completions_503_when_no_provider(make_registry, client):
    make_registry(FakeProvider("alpha", ["only-this"]))
    r = await client.post(
        "/v1/chat/completions",
        json={"model": "missing", "messages": [{"role": "user", "content": "hi"}]},
    )
    assert r.status_code == 503


@pytest.mark.asyncio
async def test_chat_completions_502_when_all_providers_fail(make_registry, client):
    p = FakeProvider(
        "alpha",
        ["m1"],
        responses=[ProviderError("oops", retryable=True)],
    )
    make_registry(p)
    r = await client.post(
        "/v1/chat/completions",
        json={"model": "m1", "messages": [{"role": "user", "content": "hi"}]},
    )
    assert r.status_code == 502


@pytest.mark.asyncio
async def test_streaming_returns_event_stream(make_registry, client):
    """Streaming was 501 in Phase 1 — now serves SSE. Full coverage in test_streaming.py."""
    make_registry(FakeProvider("alpha", ["m1"]))
    r = await client.post(
        "/v1/chat/completions",
        json={
            "model": "m1",
            "stream": True,
            "messages": [{"role": "user", "content": "hi"}],
        },
    )
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    assert "[DONE]" in r.text
