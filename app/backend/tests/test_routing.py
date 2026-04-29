"""Tests for the routing engine: alias resolution, fallback, circuit breaker."""

from __future__ import annotations

import pytest

from src.api.schemas import ChatCompletionRequest, ChatMessage
from src.providers.base import ProviderError, ProviderResponse
from src.routing.router import AllProvidersFailed, NoProviderAvailable, route
from tests.conftest import FakeProvider


@pytest.mark.asyncio
async def test_concrete_model_routes_to_supporting_provider(make_registry):
    p1 = FakeProvider("alpha", ["model-a"])
    p2 = FakeProvider("beta", ["model-b"])
    make_registry(p1, p2)

    req = ChatCompletionRequest(
        model="model-b", messages=[ChatMessage(role="user", content="hi")]
    )
    resp = await route(req, fallback_enabled=False)

    assert resp.gateway is not None
    assert resp.gateway.provider == "beta"
    assert resp.gateway.upstream_model == "model-b"
    assert resp.gateway.fallback_used is False
    assert len(p1.calls) == 0
    assert len(p2.calls) == 1


@pytest.mark.asyncio
async def test_fallback_to_next_provider_on_retryable_error(make_registry):
    p1 = FakeProvider(
        "alpha", ["shared"], responses=[ProviderError("rate limited", retryable=True)]
    )
    p2 = FakeProvider("beta", ["shared"])
    make_registry(p1, p2)

    req = ChatCompletionRequest(model="shared", messages=[ChatMessage(role="user", content="hi")])
    resp = await route(req, fallback_enabled=True)

    assert resp.gateway is not None
    assert resp.gateway.provider == "beta"
    assert resp.gateway.fallback_used is True
    assert resp.gateway.attempts == ["alpha:shared", "beta:shared"]


@pytest.mark.asyncio
async def test_non_retryable_error_does_not_fallback(make_registry):
    p1 = FakeProvider(
        "alpha",
        ["shared"],
        responses=[ProviderError("bad request", retryable=False)],
    )
    p2 = FakeProvider("beta", ["shared"])
    make_registry(p1, p2)

    req = ChatCompletionRequest(model="shared", messages=[ChatMessage(role="user", content="hi")])
    with pytest.raises(AllProvidersFailed):
        await route(req, fallback_enabled=True)
    assert len(p2.calls) == 0


@pytest.mark.asyncio
async def test_no_provider_for_model_raises(make_registry):
    make_registry(FakeProvider("alpha", ["only-this"]))
    req = ChatCompletionRequest(
        model="missing", messages=[ChatMessage(role="user", content="hi")]
    )
    with pytest.raises(NoProviderAvailable):
        await route(req, fallback_enabled=False)


@pytest.mark.asyncio
async def test_circuit_breaker_opens_after_threshold(make_registry):
    failures = [ProviderError("boom", retryable=True) for _ in range(5)]
    p1 = FakeProvider("alpha", ["m"], responses=failures)
    p2 = FakeProvider("beta", ["m"])
    reg = make_registry(p1, p2)

    req = ChatCompletionRequest(model="m", messages=[ChatMessage(role="user", content="hi")])
    # Drive 5 failures into p1's breaker via successful fallbacks to p2
    for _ in range(5):
        await route(req, fallback_enabled=True)

    entry = reg.get("alpha")
    assert entry is not None
    assert entry.breaker.state == "open"

    # Next request should skip alpha entirely (circuit open) and go straight to beta
    p1.calls.clear()
    resp = await route(req, fallback_enabled=True)
    assert len(p1.calls) == 0
    assert resp.gateway is not None
    assert resp.gateway.provider == "beta"


@pytest.mark.asyncio
async def test_auto_alias_picks_first_available(make_registry):
    p1 = FakeProvider("alpha", ["a-model"], default_model="a-model")
    p2 = FakeProvider("beta", ["b-model"], default_model="b-model")
    make_registry(p1, p2)

    req = ChatCompletionRequest(model="auto", messages=[ChatMessage(role="user", content="hi")])
    resp = await route(req, fallback_enabled=False)
    assert resp.gateway is not None
    assert resp.gateway.provider == "alpha"


@pytest.mark.asyncio
async def test_response_includes_usage_and_cost_when_priced(make_registry):
    # gpt-4o-mini is in the pricing table
    rsp = ProviderResponse(
        content="ok", model="gpt-4o-mini", prompt_tokens=1000, completion_tokens=500
    )
    p = FakeProvider("openai", ["gpt-4o-mini"], responses=[rsp])
    make_registry(p)
    req = ChatCompletionRequest(
        model="gpt-4o-mini", messages=[ChatMessage(role="user", content="hi")]
    )
    resp = await route(req, fallback_enabled=False)
    assert resp.usage.total_tokens == 1500
    assert resp.gateway is not None
    assert resp.gateway.cost_usd is not None
    assert resp.gateway.cost_usd > 0
