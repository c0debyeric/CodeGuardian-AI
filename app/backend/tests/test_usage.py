"""Tests for usage logging + cost tracking."""

from __future__ import annotations

import pytest

import src.auth.keystore as keystore_module
import src.auth.ratelimit as ratelimit_module
from src.auth.keystore import InMemoryKeyStore
from src.auth.models import Tenant
from src.core.config import get_settings
from src.providers.base import ProviderResponse
from src.usage.repository import get_usage_repo
from tests.conftest import FakeProvider


@pytest.fixture(autouse=True)
def _reset_auth():
    keystore_module.reset_keystore()
    ratelimit_module.reset_rate_limiter()
    settings = get_settings()
    original_auth = settings.auth_enabled
    original_admin = settings.admin_api_key
    yield
    settings.auth_enabled = original_auth
    settings.admin_api_key = original_admin
    keystore_module.reset_keystore()
    ratelimit_module.reset_rate_limiter()


def _seed(key: str = "sk-test-1") -> str:
    s = get_settings()
    s.auth_enabled = True
    s.admin_api_key = "admin-secret"
    store = InMemoryKeyStore()
    store.add_existing(
        key,
        Tenant(id="team-a", name="Team A", rpm_limit=100, tpm_limit=1_000_000),
    )
    keystore_module._store = store
    return key


@pytest.mark.asyncio
async def test_chat_completion_persists_usage_record(make_registry, client):
    key = _seed()
    rsp = ProviderResponse(
        content="ok", model="gpt-4o-mini", prompt_tokens=100, completion_tokens=50
    )
    make_registry(FakeProvider("openai", ["gpt-4o-mini"], responses=[rsp]))

    r = await client.post(
        "/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}"},
        json={"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "hi"}]},
    )
    assert r.status_code == 200, r.text

    rows = await get_usage_repo().usage_by_tenant()
    assert len(rows) == 1
    row = rows[0]
    assert row.tenant_id == "team-a"
    assert row.requests == 1
    assert row.total_tokens == 150
    assert row.cost_usd > 0  # gpt-4o-mini is in the pricing table


@pytest.mark.asyncio
async def test_admin_usage_endpoints_aggregate_correctly(make_registry, client):
    key = _seed()
    rsp = ProviderResponse(
        content="ok", model="gpt-4o-mini", prompt_tokens=10, completion_tokens=5
    )
    # 3 successful calls
    provider = FakeProvider("openai", ["gpt-4o-mini"], responses=[rsp, rsp, rsp])
    make_registry(provider)

    for _ in range(3):
        r = await client.post(
            "/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json={"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "hi"}]},
        )
        assert r.status_code == 200

    r = await client.get("/admin/usage/by-tenant", headers={"X-Admin-Key": "admin-secret"})
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1
    assert body[0]["tenant_id"] == "team-a"
    assert body[0]["requests"] == 3
    assert body[0]["total_tokens"] == 45  # 3 * 15

    r = await client.get("/admin/usage/by-model", headers={"X-Admin-Key": "admin-secret"})
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1
    assert body[0]["upstream_model"] == "gpt-4o-mini"
    assert body[0]["requests"] == 3
    assert body[0]["cost_usd"] > 0


@pytest.mark.asyncio
async def test_usage_admin_requires_admin_key(client):
    s = get_settings()
    s.auth_enabled = True
    s.admin_api_key = "admin-secret"
    r = await client.get("/admin/usage/by-tenant")
    assert r.status_code == 401
    r = await client.get("/admin/usage/by-tenant", headers={"X-Admin-Key": "wrong"})
    assert r.status_code == 401
