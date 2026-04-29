"""Tests for per-tenant monthly USD budget enforcement."""

from __future__ import annotations

import pytest

import src.auth.budget as budget_module
import src.auth.keystore as keystore_module
import src.auth.ratelimit as ratelimit_module
from src.auth.budget import check_budget, record_spend
from src.auth.keystore import InMemoryKeyStore
from src.auth.models import Tenant
from src.core.config import get_settings
from src.usage.models import UsageRecord
from src.usage.repository import get_usage_repo
from tests.conftest import FakeProvider


@pytest.fixture(autouse=True)
def _reset_state():
    keystore_module.reset_keystore()
    ratelimit_module.reset_rate_limiter()
    budget_module.get_budget_cache().clear()
    s = get_settings()
    snap = s.auth_enabled
    yield
    s.auth_enabled = snap
    keystore_module.reset_keystore()
    ratelimit_module.reset_rate_limiter()
    budget_module.get_budget_cache().clear()


def _seed_tenant(*, budget: float | None, key: str = "sk-budget-1") -> str:
    s = get_settings()
    s.auth_enabled = True
    store = InMemoryKeyStore()
    store.add_existing(
        key,
        Tenant(
            id="budget-tenant",
            name="B",
            rpm_limit=1000,
            tpm_limit=10_000_000,
            monthly_budget_usd=budget,
        ),
    )
    keystore_module._store = store
    return key


@pytest.mark.asyncio
async def test_check_budget_no_op_when_no_budget_configured():
    t = Tenant(id="x", name="x", monthly_budget_usd=None)
    decision = await check_budget(t)
    assert decision.allowed is True
    assert decision.budget_usd is None


@pytest.mark.asyncio
async def test_check_budget_allows_when_under_cap():
    t = Tenant(id="under-cap", name="x", monthly_budget_usd=10.0)
    # No usage recorded -> 0 spend, allowed
    decision = await check_budget(t)
    assert decision.allowed is True
    assert decision.spent_usd == 0.0


@pytest.mark.asyncio
async def test_check_budget_blocks_when_over_cap():
    # Insert a usage row that already exceeds the cap
    await get_usage_repo().insert(
        UsageRecord(
            request_id="req-1",
            tenant_id="over-cap",
            requested_model="m",
            upstream_provider="p",
            upstream_model="m",
            prompt_tokens=1,
            completion_tokens=1,
            total_tokens=2,
            cost_usd=15.0,  # over 10.0 cap
            latency_ms=10.0,
            cache_status="miss",
            fallback_used=False,
        )
    )
    t = Tenant(id="over-cap", name="x", monthly_budget_usd=10.0)
    decision = await check_budget(t)
    assert decision.allowed is False
    assert decision.spent_usd >= 15.0
    assert "exceeded" in (decision.reason or "")


@pytest.mark.asyncio
async def test_record_spend_updates_cache():
    cache = budget_module.get_budget_cache()
    cache.set("t1", 5.0)
    record_spend("t1", 1.5)
    assert cache.get("t1") == pytest.approx(6.5)


@pytest.mark.asyncio
async def test_record_spend_no_op_when_not_cached():
    cache = budget_module.get_budget_cache()
    record_spend("t2", 1.0)
    assert cache.get("t2") is None


@pytest.mark.asyncio
async def test_chat_completion_returns_402_when_over_budget(make_registry, client):
    # Pre-populate spend so the very first request is already over budget
    await get_usage_repo().insert(
        UsageRecord(
            request_id="req-pre",
            tenant_id="budget-tenant",
            requested_model="m1",
            upstream_provider="alpha",
            upstream_model="m1",
            prompt_tokens=1,
            completion_tokens=1,
            total_tokens=2,
            cost_usd=99.0,
            latency_ms=1.0,
            cache_status="miss",
            fallback_used=False,
        )
    )
    key = _seed_tenant(budget=1.0)
    make_registry(FakeProvider("alpha", ["m1"]))

    r = await client.post(
        "/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}"},
        json={"model": "m1", "messages": [{"role": "user", "content": "hi"}]},
    )
    assert r.status_code == 402
    body = r.json()
    assert body["detail"]["budget_usd"] == 1.0
    assert body["detail"]["spent_usd"] >= 99.0


@pytest.mark.asyncio
async def test_chat_completion_allows_when_within_budget(make_registry, client):
    key = _seed_tenant(budget=100.0)
    make_registry(FakeProvider("alpha", ["m1"]))
    r = await client.post(
        "/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}"},
        json={"model": "m1", "messages": [{"role": "user", "content": "hi"}]},
    )
    assert r.status_code == 200
