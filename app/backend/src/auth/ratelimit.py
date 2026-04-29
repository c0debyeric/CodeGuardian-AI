"""Rate limiter.

Sliding-window token-bucket style limiter with two backends:
  - InMemoryRateLimiter: process-local, fine for local dev / single-replica
  - RedisRateLimiter: distributed, used in production

Both implement the same `RateLimiter` protocol. The chosen backend is
selected by `get_rate_limiter()` based on settings.redis_url.

Two limits are tracked per tenant:
  - requests/minute (RPM)
  - tokens/minute (TPM) — cost-bearing units, charged after the call

The TPM limit is enforced *after* the request completes (we don't know token
count up-front). This is what every commercial gateway does. RPM is enforced
before-the-call to provide cheap protection.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class LimitDecision:
    allowed: bool
    reason: str | None = None
    retry_after_seconds: float | None = None


class RateLimiter(Protocol):
    async def check_request(self, tenant_id: str, *, rpm_limit: int) -> LimitDecision: ...
    async def record_tokens(self, tenant_id: str, tokens: int) -> None: ...
    async def check_tokens(self, tenant_id: str, *, tpm_limit: int) -> LimitDecision: ...


# ---------- In-memory implementation ----------


@dataclass
class _SlidingWindow:
    timestamps: deque = field(default_factory=deque)
    token_events: deque = field(default_factory=deque)  # (ts, tokens)

    def prune(self, now: float, window: float = 60.0) -> None:
        cutoff = now - window
        while self.timestamps and self.timestamps[0] < cutoff:
            self.timestamps.popleft()
        while self.token_events and self.token_events[0][0] < cutoff:
            self.token_events.popleft()


class InMemoryRateLimiter:
    """Per-tenant sliding-window limiter. Thread-unsafe; fine for dev."""

    def __init__(self) -> None:
        self._windows: dict[str, _SlidingWindow] = {}

    def _w(self, tenant_id: str) -> _SlidingWindow:
        w = self._windows.get(tenant_id)
        if w is None:
            w = _SlidingWindow()
            self._windows[tenant_id] = w
        return w

    async def check_request(self, tenant_id: str, *, rpm_limit: int) -> LimitDecision:
        now = time.monotonic()
        w = self._w(tenant_id)
        w.prune(now)
        if len(w.timestamps) >= rpm_limit:
            retry = max(0.0, 60.0 - (now - w.timestamps[0]))
            return LimitDecision(
                False, reason=f"rpm limit {rpm_limit}/min exceeded", retry_after_seconds=retry
            )
        w.timestamps.append(now)
        return LimitDecision(True)

    async def check_tokens(self, tenant_id: str, *, tpm_limit: int) -> LimitDecision:
        now = time.monotonic()
        w = self._w(tenant_id)
        w.prune(now)
        used = sum(t for _, t in w.token_events)
        if used >= tpm_limit:
            retry = max(0.0, 60.0 - (now - w.token_events[0][0])) if w.token_events else 0.0
            return LimitDecision(
                False,
                reason=f"tpm limit {tpm_limit}/min exceeded (used {used})",
                retry_after_seconds=retry,
            )
        return LimitDecision(True)

    async def record_tokens(self, tenant_id: str, tokens: int) -> None:
        if tokens <= 0:
            return
        now = time.monotonic()
        w = self._w(tenant_id)
        w.prune(now)
        w.token_events.append((now, tokens))


# ---------- Redis implementation ----------


class RedisRateLimiter:
    """Redis-backed sliding-window limiter using sorted sets.

    For each tenant we keep two sorted sets:
      - rl:req:<tenant>   — score=ts (sec), member=unique
      - rl:tok:<tenant>   — score=ts, member=ts:uuid, value-encoded token count

    The token tally is approximated by storing one entry per chargeable
    request. For higher precision, use HINCRBY with per-second buckets.
    """

    def __init__(self, redis_client) -> None:  # redis.asyncio.Redis
        self._r = redis_client

    @staticmethod
    def _req_key(tid: str) -> str:
        return f"rl:req:{tid}"

    @staticmethod
    def _tok_key(tid: str) -> str:
        return f"rl:tok:{tid}"

    async def check_request(self, tenant_id: str, *, rpm_limit: int) -> LimitDecision:
        now = time.time()
        cutoff = now - 60
        key = self._req_key(tenant_id)
        async with self._r.pipeline(transaction=False) as p:
            p.zremrangebyscore(key, 0, cutoff)
            p.zcard(key)
            _, count = await p.execute()
        if int(count) >= rpm_limit:
            return LimitDecision(False, reason=f"rpm limit {rpm_limit}/min exceeded")
        # Add a token now (monotonically unique member)
        await self._r.zadd(key, {f"{now}:{int(now * 1e6)}": now})
        await self._r.expire(key, 120)
        return LimitDecision(True)

    async def check_tokens(self, tenant_id: str, *, tpm_limit: int) -> LimitDecision:
        now = time.time()
        cutoff = now - 60
        key = self._tok_key(tenant_id)
        async with self._r.pipeline(transaction=False) as p:
            p.zremrangebyscore(key, 0, cutoff)
            p.zrange(key, 0, -1, withscores=False)
            await p.execute()
        # Sum tokens encoded in members "tokens:ts"
        members = await self._r.zrange(key, 0, -1)
        used = 0
        for m in members:
            try:
                tok_str = m.split(b":", 1)[0] if isinstance(m, bytes) else m.split(":", 1)[0]
                used += int(tok_str)
            except (ValueError, IndexError):
                continue
        if used >= tpm_limit:
            return LimitDecision(False, reason=f"tpm limit {tpm_limit}/min exceeded (used {used})")
        return LimitDecision(True)

    async def record_tokens(self, tenant_id: str, tokens: int) -> None:
        if tokens <= 0:
            return
        now = time.time()
        key = self._tok_key(tenant_id)
        member = f"{tokens}:{now}"
        await self._r.zadd(key, {member: now})
        await self._r.expire(key, 120)


# ---------- Selector ----------


_limiter: RateLimiter | None = None


def get_rate_limiter() -> RateLimiter:
    """Return the configured rate limiter, defaulting to in-memory."""
    global _limiter
    if _limiter is None:
        from src.core.config import get_settings

        settings = get_settings()
        if settings.redis_url:
            try:
                import redis.asyncio as redis_async  # type: ignore[import-untyped]

                client = redis_async.from_url(settings.redis_url, decode_responses=False)
                _limiter = RedisRateLimiter(client)
            except ImportError:
                _limiter = InMemoryRateLimiter()
        else:
            _limiter = InMemoryRateLimiter()
    return _limiter


def reset_rate_limiter() -> None:
    global _limiter
    _limiter = None
