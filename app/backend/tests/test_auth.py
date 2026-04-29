"""Tests for auth + rate limiting."""

from __future__ import annotations

import pytest

import src.auth.keystore as keystore_module
import src.auth.ratelimit as ratelimit_module
from src.auth.keystore import InMemoryKeyStore
from src.auth.models import Tenant
from src.auth.ratelimit import InMemoryRateLimiter
from src.core.config import get_settings
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


def _enable_auth(*, admin_key: str | None = None) -> None:
    s = get_settings()
    s.auth_enabled = True
    if admin_key is not None:
        s.admin_api_key = admin_key


def _seed_tenant(tenant: Tenant, key: str = "sk-test-1") -> str:
    store = InMemoryKeyStore()
    store.add_existing(key, tenant)
    keystore_module._store = store
    return key


@pytest.mark.asyncio
async def test_auth_disabled_allows_anonymous(make_registry, client):
    make_registry(FakeProvider("alpha", ["m1"]))
    r = await client.post(
        "/v1/chat/completions",
        json={"model": "m1", "messages": [{"role": "user", "content": "hi"}]},
    )
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_auth_enabled_requires_bearer(make_registry, client):
    _enable_auth()
    make_registry(FakeProvider("alpha", ["m1"]))
    r = await client.post(
        "/v1/chat/completions",
        json={"model": "m1", "messages": [{"role": "user", "content": "hi"}]},
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_valid_key_succeeds_and_rejects_disallowed_model(make_registry, client):
    _enable_auth()
    key = _seed_tenant(
        Tenant(
            id="t1",
            name="T1",
            rpm_limit=5,
            tpm_limit=1000,
            allowed_models=["m1"],
        )
    )
    make_registry(FakeProvider("alpha", ["m1", "m2"]))

    r = await client.post(
        "/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}"},
        json={"model": "m1", "messages": [{"role": "user", "content": "hi"}]},
    )
    assert r.status_code == 200, r.text

    r = await client.post(
        "/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}"},
        json={"model": "m2", "messages": [{"role": "user", "content": "hi"}]},
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_rpm_limit_enforced(make_registry, client):
    _enable_auth()
    key = _seed_tenant(Tenant(id="t1", name="T1", rpm_limit=2, tpm_limit=1_000_000))
    make_registry(FakeProvider("alpha", ["m1"]))

    for _ in range(2):
        r = await client.post(
            "/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json={"model": "m1", "messages": [{"role": "user", "content": "hi"}]},
        )
        assert r.status_code == 200

    r = await client.post(
        "/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}"},
        json={"model": "m1", "messages": [{"role": "user", "content": "hi"}]},
    )
    assert r.status_code == 429
    assert "Retry-After" in r.headers


@pytest.mark.asyncio
async def test_tpm_limit_enforced_after_usage(make_registry, client):
    _enable_auth()
    key = _seed_tenant(Tenant(id="t1", name="T1", rpm_limit=100, tpm_limit=20))
    # FakeProvider returns 15 total tokens by default (10 in + 5 out)
    make_registry(FakeProvider("alpha", ["m1"]))

    # 1st call: pre-check used=0 < 20 → allowed; charges 15
    # 2nd call: pre-check used=15 < 20 → allowed; charges 30
    # 3rd call: pre-check used=30 >= 20 → 429
    for expected in (200, 200, 429):
        r = await client.post(
            "/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json={"model": "m1", "messages": [{"role": "user", "content": "hi"}]},
        )
        assert r.status_code == expected, r.text


@pytest.mark.asyncio
async def test_admin_create_tenant_requires_admin_key(client):
    _enable_auth(admin_key="admin-secret")
    r = await client.post(
        "/admin/tenants",
        json={"id": "team1", "name": "Team One"},
    )
    assert r.status_code == 401

    r = await client.post(
        "/admin/tenants",
        headers={"X-Admin-Key": "admin-secret"},
        json={"id": "team1", "name": "Team One"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["tenant_id"] == "team1"
    assert body["api_key"].startswith("sk-team1-")


@pytest.mark.asyncio
async def test_admin_disabled_when_no_admin_key_configured(client):
    _enable_auth()  # auth on, admin_api_key=None
    r = await client.post(
        "/admin/tenants",
        headers={"X-Admin-Key": "anything"},
        json={"id": "team1", "name": "Team One"},
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_in_memory_limiter_recovers_after_window():
    """Sanity check on the limiter without HTTP layer."""
    limiter = InMemoryRateLimiter()
    for _ in range(3):
        d = await limiter.check_request("t", rpm_limit=3)
        assert d.allowed
    d = await limiter.check_request("t", rpm_limit=3)
    assert not d.allowed
