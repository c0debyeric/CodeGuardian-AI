"""Tests for OpenAI-compatible SSE streaming responses."""

from __future__ import annotations

import json

import pytest

from src.providers.base import ProviderResponse
from tests.conftest import FakeProvider


def _parse_sse(body: str) -> list[dict | str]:
    """Parse an SSE body into a list of decoded JSON payloads (or '[DONE]')."""
    out: list[dict | str] = []
    for line in body.splitlines():
        if not line.startswith("data: "):
            continue
        data = line[len("data: "):]
        if data == "[DONE]":
            out.append("[DONE]")
        else:
            out.append(json.loads(data))
    return out


@pytest.mark.asyncio
async def test_streaming_returns_sse_event_stream(make_registry, client):
    make_registry(
        FakeProvider(
            "alpha",
            ["m1"],
            responses=[
                ProviderResponse(
                    content="hello world from gateway",
                    model="m1",
                    prompt_tokens=4,
                    completion_tokens=4,
                )
            ],
        )
    )
    r = await client.post(
        "/v1/chat/completions",
        json={"model": "m1", "messages": [{"role": "user", "content": "hi"}], "stream": True},
    )
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")

    events = _parse_sse(r.text)
    assert events[-1] == "[DONE]"
    # First chunk announces role
    assert events[0]["choices"][0]["delta"] == {"role": "assistant"}
    # Penultimate chunk has finish_reason
    assert events[-2]["choices"][0]["finish_reason"] == "stop"
    # Reassembled content matches the upstream response
    content = "".join(
        e["choices"][0]["delta"].get("content", "")
        for e in events[1:-2]
        if isinstance(e, dict)
    )
    assert content == "hello world from gateway"


@pytest.mark.asyncio
async def test_streaming_records_usage_and_metrics(make_registry, client):
    from prometheus_client import REGISTRY

    make_registry(
        FakeProvider(
            "alpha",
            ["m1"],
            responses=[
                ProviderResponse(
                    content="abc", model="m1", prompt_tokens=10, completion_tokens=2
                )
            ],
        )
    )
    before = REGISTRY.get_sample_value(
        "llm_requests_total",
        {
            "tenant": "anonymous",
            "requested_model": "m1",
            "provider": "alpha",
            "upstream_model": "m1",
            "status": "200",
        },
    ) or 0.0

    r = await client.post(
        "/v1/chat/completions",
        json={"model": "m1", "messages": [{"role": "user", "content": "hi"}], "stream": True},
    )
    assert r.status_code == 200
    # Drain
    _ = r.text

    after = REGISTRY.get_sample_value(
        "llm_requests_total",
        {
            "tenant": "anonymous",
            "requested_model": "m1",
            "provider": "alpha",
            "upstream_model": "m1",
            "status": "200",
        },
    )
    assert after is not None and after - before == pytest.approx(1.0)
