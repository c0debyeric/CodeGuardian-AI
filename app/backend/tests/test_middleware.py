"""Tests for cache + guardrails middleware."""

from __future__ import annotations

import pytest

import src.auth.keystore as keystore_module
import src.auth.ratelimit as ratelimit_module
import src.middleware.cache as cache_module
from src.api.schemas import ChatCompletionRequest, ChatMessage
from src.auth.keystore import InMemoryKeyStore
from src.auth.models import Tenant
from src.core.config import get_settings
from src.middleware.cache import cache_key
from src.middleware.guardrails import apply_to_messages, redact_pii
from src.providers.base import ProviderResponse
from tests.conftest import FakeProvider


@pytest.fixture(autouse=True)
def _reset_state():
    keystore_module.reset_keystore()
    ratelimit_module.reset_rate_limiter()
    cache_module.reset_cache()
    s = get_settings()
    snap = (s.auth_enabled, s.admin_api_key, s.guardrails_enabled, s.semantic_cache_enabled)
    yield
    s.auth_enabled, s.admin_api_key, s.guardrails_enabled, s.semantic_cache_enabled = snap
    keystore_module.reset_keystore()
    ratelimit_module.reset_rate_limiter()
    cache_module.reset_cache()


# ---------- Guardrails unit tests ----------


def test_redact_pii_ssn_and_email():
    r = redact_pii("SSN 123-45-6789 contact me at jane@example.com")
    assert "123-45-6789" not in r.text
    assert "jane@example.com" not in r.text
    assert "ssn" in r.detected
    assert "email" in r.detected
    assert r.redacted is True


def test_redact_pii_no_match_returns_unchanged():
    r = redact_pii("hello world, no PII here")
    assert r.text == "hello world, no PII here"
    assert r.detected == []
    assert r.redacted is False


def test_apply_to_messages_dedupes_detected_types():
    msgs = [
        ChatMessage(role="user", content="email me at a@b.com"),
        ChatMessage(role="user", content="or at c@d.com"),
    ]
    new_msgs, detected = apply_to_messages(msgs, redact=True)
    assert detected == ["email"]
    assert "a@b.com" not in new_msgs[0].content
    assert "c@d.com" not in new_msgs[1].content


# ---------- Cache unit tests ----------


def test_cache_key_stable_across_equivalent_requests():
    a = ChatCompletionRequest(
        model="m1",
        messages=[ChatMessage(role="user", content="hello")],
        temperature=0.5,
    )
    b = ChatCompletionRequest(
        model="m1",
        messages=[ChatMessage(role="user", content="hello")],
        temperature=0.5,
    )
    assert cache_key(a) == cache_key(b)


def test_cache_key_differs_when_messages_change():
    a = ChatCompletionRequest(model="m1", messages=[ChatMessage(role="user", content="hi")])
    b = ChatCompletionRequest(model="m1", messages=[ChatMessage(role="user", content="bye")])
    assert cache_key(a) != cache_key(b)


# ---------- Integration tests via API ----------


def _seed(key: str = "sk-test-1") -> str:
    s = get_settings()
    s.auth_enabled = True
    s.admin_api_key = "admin-secret"
    store = InMemoryKeyStore()
    store.add_existing(
        key, Tenant(id="team-a", name="A", rpm_limit=100, tpm_limit=1_000_000)
    )
    keystore_module._store = store
    return key


@pytest.mark.asyncio
async def test_guardrails_redact_before_provider_call(make_registry, client):
    s = get_settings()
    s.guardrails_enabled = True
    key = _seed()
    p = FakeProvider("alpha", ["m1"])
    make_registry(p)

    r = await client.post(
        "/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}"},
        json={
            "model": "m1",
            "messages": [{"role": "user", "content": "my SSN is 111-22-3333"}],
        },
    )
    assert r.status_code == 200
    # Provider received the *redacted* prompt
    assert len(p.calls) == 1
    upstream_msg = p.calls[0][1].messages[0].content
    assert "111-22-3333" not in upstream_msg
    assert "[REDACTED:SSN]" in upstream_msg


@pytest.mark.asyncio
async def test_cache_hit_avoids_provider_call(make_registry, client):
    s = get_settings()
    s.semantic_cache_enabled = True
    key = _seed()
    rsp = ProviderResponse(content="cached me", model="m1", prompt_tokens=5, completion_tokens=2)
    p = FakeProvider("alpha", ["m1"], responses=[rsp])
    make_registry(p)

    body = {"model": "m1", "messages": [{"role": "user", "content": "what is 2+2"}]}

    r1 = await client.post(
        "/v1/chat/completions", headers={"Authorization": f"Bearer {key}"}, json=body
    )
    assert r1.status_code == 200
    assert r1.json()["gateway"]["cache"] == "miss"

    r2 = await client.post(
        "/v1/chat/completions", headers={"Authorization": f"Bearer {key}"}, json=body
    )
    assert r2.status_code == 200
    assert r2.json()["gateway"]["cache"] == "hit"
    # Provider only called once
    assert len(p.calls) == 1


@pytest.mark.asyncio
async def test_cache_disabled_by_default(make_registry, client):
    key = _seed()
    p = FakeProvider("alpha", ["m1"])
    make_registry(p)
    body = {"model": "m1", "messages": [{"role": "user", "content": "hi"}]}
    for _ in range(2):
        r = await client.post(
            "/v1/chat/completions", headers={"Authorization": f"Bearer {key}"}, json=body
        )
        assert r.status_code == 200
        assert r.json()["gateway"]["cache"] == "miss"
    assert len(p.calls) == 2
