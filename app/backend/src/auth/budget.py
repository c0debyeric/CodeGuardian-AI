"""Per-tenant monthly USD budget enforcement.

Why this lives in its own module:
  - The check needs both the keystore (tenant.monthly_budget_usd) and the
    usage repo (month-to-date cost) — neither owns the other.
  - We add a small TTL cache so we don't hammer Postgres on every request.
    A 30-second staleness window is acceptable for a soft cap; the
    consequence of being a few seconds late is at most a few extra requests.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from src.auth.models import Tenant
from src.usage.repository import get_usage_repo


@dataclass
class BudgetDecision:
    allowed: bool
    spent_usd: float
    budget_usd: float | None
    reason: str | None = None


class _MtdCostCache:
    """Tiny in-process TTL cache for month-to-date cost lookups."""

    def __init__(self, ttl_seconds: float = 30.0) -> None:
        self._ttl = ttl_seconds
        self._data: dict[str, tuple[float, float]] = {}  # tenant_id -> (cost, expires_at)

    def get(self, tenant_id: str) -> float | None:
        v = self._data.get(tenant_id)
        if v is None:
            return None
        cost, expires_at = v
        if expires_at < time.monotonic():
            return None
        return cost

    def set(self, tenant_id: str, cost: float) -> None:
        self._data[tenant_id] = (cost, time.monotonic() + self._ttl)

    def invalidate(self, tenant_id: str) -> None:
        self._data.pop(tenant_id, None)

    def clear(self) -> None:
        self._data.clear()


_cache = _MtdCostCache()


def get_budget_cache() -> _MtdCostCache:
    return _cache


async def check_budget(tenant: Tenant) -> BudgetDecision:
    """Return whether the tenant is under their monthly USD budget.

    No-op (allowed) when the tenant has no budget configured. The check is
    a simple `current_spend < budget`; we don't try to estimate the cost
    of the in-flight request because we don't know the response token count
    until the provider replies. The hard stop happens *before* the call.
    """
    budget = tenant.monthly_budget_usd
    if budget is None or budget <= 0:
        return BudgetDecision(allowed=True, spent_usd=0.0, budget_usd=budget)

    spent = _cache.get(tenant.id)
    if spent is None:
        spent = await get_usage_repo().month_to_date_cost(tenant.id)
        _cache.set(tenant.id, spent)

    if spent >= budget:
        return BudgetDecision(
            allowed=False,
            spent_usd=spent,
            budget_usd=budget,
            reason=(
                f"monthly budget exceeded: ${spent:.4f} spent "
                f"of ${budget:.2f} cap"
            ),
        )
    return BudgetDecision(allowed=True, spent_usd=spent, budget_usd=budget)


def record_spend(tenant_id: str, cost_usd: float) -> None:
    """Increment the cached month-to-date spend after a successful request.

    Avoids waiting for the next cache miss to reflect the new spend; without
    this, a tenant could blow far past budget in the 30-second window.
    """
    if cost_usd <= 0:
        return
    cur = _cache.get(tenant_id)
    if cur is None:
        return  # not in cache yet; next request will populate it from DB
    _cache.set(tenant_id, cur + cost_usd)
