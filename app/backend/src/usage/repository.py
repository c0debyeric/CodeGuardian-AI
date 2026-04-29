"""Repository for usage records.

Only writes happen on the hot path (chat completion). Reads happen from the
admin dashboard / Prometheus exporter, never from the request path.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from src.usage.db import get_session_factory
from src.usage.models import UsageRecord


@dataclass
class TenantUsageSummary:
    tenant_id: str
    requests: int
    total_tokens: int
    cost_usd: float


class UsageRepository:
    async def insert(self, record: UsageRecord) -> None:
        factory = get_session_factory()
        async with factory() as session:
            session.add(record)
            await session.commit()

    async def usage_by_tenant(
        self, *, since: datetime | None = None
    ) -> list[TenantUsageSummary]:
        if since is None:
            since = datetime.now(timezone.utc) - timedelta(hours=24)
        factory = get_session_factory()
        async with factory() as session:
            stmt = (
                select(
                    UsageRecord.tenant_id,
                    func.count(UsageRecord.id),
                    func.coalesce(func.sum(UsageRecord.total_tokens), 0),
                    func.coalesce(func.sum(UsageRecord.cost_usd), 0.0),
                )
                .where(UsageRecord.ts >= since)
                .group_by(UsageRecord.tenant_id)
            )
            result = await session.execute(stmt)
            return [
                TenantUsageSummary(
                    tenant_id=row[0], requests=row[1], total_tokens=row[2], cost_usd=row[3]
                )
                for row in result.all()
            ]

    async def usage_by_model(
        self, *, since: datetime | None = None
    ) -> list[tuple[str, int, float]]:
        if since is None:
            since = datetime.now(timezone.utc) - timedelta(hours=24)
        factory = get_session_factory()
        async with factory() as session:
            stmt = (
                select(
                    UsageRecord.upstream_model,
                    func.count(UsageRecord.id),
                    func.coalesce(func.sum(UsageRecord.cost_usd), 0.0),
                )
                .where(UsageRecord.ts >= since)
                .group_by(UsageRecord.upstream_model)
            )
            result = await session.execute(stmt)
            return [(row[0], row[1], row[2]) for row in result.all()]

    async def recent(self, *, limit: int = 50) -> list[UsageRecord]:
        """Most recent N records, newest first. Powers the admin live log view."""
        factory = get_session_factory()
        async with factory() as session:
            stmt = select(UsageRecord).order_by(UsageRecord.ts.desc()).limit(limit)
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def month_to_date_cost(self, tenant_id: str) -> float:
        """Sum cost_usd for `tenant_id` since the start of the current UTC month.

        Used by the per-tenant monthly budget enforcement check. The query is
        indexed on (tenant_id, ts) so it stays cheap even with millions of rows.
        """
        now = datetime.now(timezone.utc)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        factory = get_session_factory()
        async with factory() as session:
            stmt = select(func.coalesce(func.sum(UsageRecord.cost_usd), 0.0)).where(
                UsageRecord.tenant_id == tenant_id,
                UsageRecord.ts >= month_start,
            )
            result = await session.execute(stmt)
            return float(result.scalar() or 0.0)


_repo: UsageRepository | None = None


def get_usage_repo() -> UsageRepository:
    global _repo
    if _repo is None:
        _repo = UsageRepository()
    return _repo


def reset_usage_repo() -> None:
    global _repo
    _repo = None
