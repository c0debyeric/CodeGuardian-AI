"""Usage record schema (DB row)."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class UsageRecord(Base):
    """One row per LLM request handled by the gateway.

    Indexed on (tenant_id, ts) so the dashboard query "show me usage for
    team X in the last 24h" is a single index range scan.
    """

    __tablename__ = "usage_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )
    request_id: Mapped[str] = mapped_column(String(64), index=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    requested_model: Mapped[str] = mapped_column(String(128))
    upstream_provider: Mapped[str] = mapped_column(String(64))
    upstream_model: Mapped[str] = mapped_column(String(128))
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    cache_status: Mapped[str] = mapped_column(String(16), default="miss")
    fallback_used: Mapped[bool] = mapped_column(default=False)
    status_code: Mapped[int] = mapped_column(Integer, default=200)
