"""Tests for Prometheus metrics integration."""

from __future__ import annotations

import pytest
from prometheus_client import REGISTRY

import src.auth.keystore as keystore_module
import src.auth.ratelimit as ratelimit_module
import src.middleware.cache as cache_module
from src.auth.keystore import InMemoryKeyStore
from src.auth.models import Tenant
from src.core.config import get_settings
from tests.conftest import FakeProvider


@pytest.fixture(autouse=True)
def _reset_state():
    keystore_module.reset_keystore()
    ratelimit_module.reset_rate_limiter()
    cache_module.reset_cache()
    s = get_settings()
    snap = (s.auth_enabled, s.guardrails_enabled, s.semantic_cache_enabled)
    yield
    s.auth_enabled, s.guardrails_enabled, s.semantic_cache_enabled = snap
    keystore_module.reset_keystore()
    ratelimit_module.reset_rate_limiter()
    cache_module.reset_cache()


def _seed(key: str = "sk-metrics-1") -> str:
    s = get_settings()
    s.auth_enabled = True
    store = InMemoryKeyStore()
    store.add_existing(
        key, Tenant(id="metric-tenant", name="M", rpm_limit=1000, tpm_limit=10_000_000)
    )
    keystore_module._store = store
    return key


def _metric_value(name: str, **labels: str) -> float:
    """Read a counter value by name + labels; 0 if not present."""
    val = REGISTRY.get_sample_value(name, labels=labels)
    return float(val) if val is not None else 0.0


@pytest.mark.asyncio
async def test_chat_completion_increments_request_and_token_counters(make_registry, client):
    key = _seed()
    make_registry(FakeProvider("alpha", ["m1"]))

    before_req = _metric_value(
        "llm_requests_total",
        tenant="metric-tenant",
        requested_model="m1",
        provider="alpha",
        upstream_model="m1",
        status="200",
    )
    before_prompt = _metric_value(
        "llm_tokens_total",
        tenant="metric-tenant",
        provider="alpha",
        upstream_model="m1",
        direction="prompt",
    )

    r = await client.post(
        "/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}"},
        json={"model": "m1", "messages": [{"role": "user", "content": "hi"}]},
    )
    assert r.status_code == 200

    after_req = _metric_value(
        "llm_requests_total",
        tenant="metric-tenant",
        requested_model="m1",
        provider="alpha",
        upstream_model="m1",
        status="200",
    )
    after_prompt = _metric_value(
        "llm_tokens_total",
        tenant="metric-tenant",
        provider="alpha",
        upstream_model="m1",
        direction="prompt",
    )
    assert after_req == before_req + 1
    assert after_prompt == before_prompt + 10  # FakeProvider default: 10 prompt tokens


@pytest.mark.asyncio
async def test_cache_hit_increments_cache_event_counter(make_registry, client):
    s = get_settings()
    s.semantic_cache_enabled = True
    key = _seed()
    make_registry(FakeProvider("alpha", ["m1"]))

    body = {"model": "m1", "messages": [{"role": "user", "content": "ping"}]}
    await client.post("/v1/chat/completions", headers={"Authorization": f"Bearer {key}"}, json=body)

    before_hits = _metric_value(
        "llm_cache_events_total", tenant="metric-tenant", event="hit"
    )
    await client.post("/v1/chat/completions", headers={"Authorization": f"Bearer {key}"}, json=body)
    after_hits = _metric_value(
        "llm_cache_events_total", tenant="metric-tenant", event="hit"
    )
    assert after_hits == before_hits + 1


@pytest.mark.asyncio
async def test_metrics_endpoint_exposes_llm_metrics(make_registry, client):
    key = _seed()
    make_registry(FakeProvider("alpha", ["m1"]))
    await client.post(
        "/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}"},
        json={"model": "m1", "messages": [{"role": "user", "content": "hi"}]},
    )
    r = await client.get("/metrics")
    assert r.status_code == 200
    text = r.text
    assert "llm_requests_total" in text
    assert "llm_tokens_total" in text
    assert "llm_request_duration_seconds" in text
