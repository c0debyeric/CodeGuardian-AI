"""Tests for embedding-based semantic cache."""

from __future__ import annotations

import pytest

import src.middleware.cache as cache_module
from src.core.config import get_settings
from src.middleware.cache import SemanticCache, prompt_text
from src.middleware.embeddings import HashingEmbedder, cosine, set_embedder
from src.providers.base import ProviderResponse
from tests.conftest import FakeProvider


@pytest.fixture(autouse=True)
def _reset():
    set_embedder(HashingEmbedder(dim=256))
    cache_module.reset_cache()
    s = get_settings()
    snap = (s.semantic_cache_enabled, s.semantic_cache_mode, s.semantic_cache_threshold)
    yield
    s.semantic_cache_enabled, s.semantic_cache_mode, s.semantic_cache_threshold = snap
    cache_module.reset_cache()
    set_embedder(None)


def test_hashing_embedder_is_deterministic_and_normalized():
    e = HashingEmbedder(dim=64)
    v1 = e.embed("hello world")
    v2 = e.embed("hello world")
    assert v1 == v2
    # L2 norm ~= 1
    assert abs(sum(x * x for x in v1) - 1.0) < 1e-9


def test_cosine_self_similarity_is_one():
    e = HashingEmbedder(dim=64)
    v = e.embed("the quick brown fox")
    assert cosine(v, v) == pytest.approx(1.0)


def test_cosine_disjoint_vocab_is_low():
    e = HashingEmbedder(dim=512)
    a = e.embed("the capital of france is paris")
    b = e.embed("kubernetes pod scheduling autoscaler")
    assert cosine(a, b) < 0.2


@pytest.mark.asyncio
async def test_semantic_cache_hits_on_paraphrase():
    """Word-overlap paraphrase should match above threshold."""
    cache = SemanticCache(threshold=0.6, max_entries=100)
    from src.api.schemas import (
        ChatCompletionResponse,
        Choice,
        ChoiceMessage,
        GatewayMeta,
        Usage,
    )

    completion = ChatCompletionResponse(
        id="c1",
        created=0,
        model="m1",
        choices=[
            Choice(
                index=0, message=ChoiceMessage(role="assistant", content="Paris"), finish_reason="stop"
            )
        ],
        usage=Usage(prompt_tokens=5, completion_tokens=1, total_tokens=6),
        gateway=GatewayMeta(provider="alpha", upstream_model="m1", latency_ms=1.0, cache="miss", fallback_used=False),
    )

    await cache.set_semantic(
        namespace="m1",
        text="What is the capital of France?",
        value=completion,
        ttl=3600,
    )

    hit = await cache.get_semantic(
        namespace="m1", text="what's the capital of france"
    )
    assert hit is not None
    response, sim = hit
    assert response.choices[0].message.content == "Paris"
    assert sim >= 0.6


@pytest.mark.asyncio
async def test_semantic_cache_misses_unrelated_prompt():
    cache = SemanticCache(threshold=0.6, max_entries=100)
    from src.api.schemas import (
        ChatCompletionResponse,
        Choice,
        ChoiceMessage,
        GatewayMeta,
        Usage,
    )

    completion = ChatCompletionResponse(
        id="c1",
        created=0,
        model="m1",
        choices=[
            Choice(
                index=0, message=ChoiceMessage(role="assistant", content="Paris"), finish_reason="stop"
            )
        ],
        usage=Usage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
        gateway=GatewayMeta(provider="alpha", upstream_model="m1", latency_ms=1.0, cache="miss", fallback_used=False),
    )
    await cache.set_semantic(
        namespace="m1", text="what is the capital of france", value=completion, ttl=3600
    )
    miss = await cache.get_semantic(
        namespace="m1", text="explain kubernetes pod scheduling"
    )
    assert miss is None


@pytest.mark.asyncio
async def test_semantic_cache_namespaced_by_model():
    """A response cached for model A must not leak to a request for model B."""
    cache = SemanticCache(threshold=0.0, max_entries=100)
    from src.api.schemas import (
        ChatCompletionResponse,
        Choice,
        ChoiceMessage,
        GatewayMeta,
        Usage,
    )

    completion = ChatCompletionResponse(
        id="c1",
        created=0,
        model="claude",
        choices=[
            Choice(
                index=0, message=ChoiceMessage(role="assistant", content="x"), finish_reason="stop"
            )
        ],
        usage=Usage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
        gateway=GatewayMeta(provider="bedrock", upstream_model="claude", latency_ms=1.0, cache="miss", fallback_used=False),
    )
    await cache.set_semantic(namespace="claude", text="hello", value=completion, ttl=3600)
    assert await cache.get_semantic(namespace="gpt-4", text="hello") is None
    assert await cache.get_semantic(namespace="claude", text="hello") is not None


@pytest.mark.asyncio
async def test_chat_route_uses_semantic_cache_end_to_end(make_registry, client):
    """Two requests with paraphrased prompts: second should be a cache hit."""
    s = get_settings()
    s.semantic_cache_enabled = True
    s.semantic_cache_mode = "semantic"
    s.semantic_cache_threshold = 0.6

    make_registry(
        FakeProvider(
            "alpha",
            ["m1"],
            responses=[
                ProviderResponse(content="Paris", model="m1", prompt_tokens=5, completion_tokens=1),
                # Provider should NOT be called a second time. If it is, this empty
                # response list will cause the FakeProvider's default echo to fire,
                # but the gateway.cache field will reveal it was a miss.
            ],
        )
    )

    r1 = await client.post(
        "/v1/chat/completions",
        json={"model": "m1", "messages": [{"role": "user", "content": "What is the capital of France?"}]},
    )
    assert r1.status_code == 200
    assert r1.json()["gateway"]["cache"] == "miss"

    r2 = await client.post(
        "/v1/chat/completions",
        json={"model": "m1", "messages": [{"role": "user", "content": "what's the capital of france"}]},
    )
    assert r2.status_code == 200
    body2 = r2.json()
    assert body2["gateway"]["cache"] == "hit"
    assert body2["choices"][0]["message"]["content"] == "Paris"


def test_prompt_text_concatenates_messages():
    from src.api.schemas import ChatCompletionRequest
    from src.api.schemas import ChatMessage as _Msg  # request-side message type

    req = ChatCompletionRequest(
        model="m",
        messages=[
            _Msg(role="system", content="be brief"),
            _Msg(role="user", content="hi"),
        ],
    )
    text = prompt_text(req)
    assert "be brief" in text
    assert "hi" in text
