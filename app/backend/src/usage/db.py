"""Async DB engine + session factory.

The DB URL comes from settings.database_url. Examples:
  - sqlite+aiosqlite:///./gateway.db   (local dev / tests)
  - postgresql+asyncpg://user:pw@host/db (prod, RDS)
"""

from __future__ import annotations

import structlog
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.core.config import get_settings
from src.usage.models import Base

logger = structlog.get_logger(__name__)


_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _resolve_url() -> str:
    """Return effective DB URL. Defaults to in-memory SQLite when unset."""
    settings = get_settings()
    if settings.database_url:
        return settings.database_url
    return "sqlite+aiosqlite:///:memory:"


async def init_db() -> None:
    """Create tables if they don't exist. Called at startup."""
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("db.initialized", url=_redacted_url())


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = create_async_engine(_resolve_url(), pool_pre_ping=True, future=True)
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            get_engine(), expire_on_commit=False, class_=AsyncSession
        )
    return _session_factory


async def reset_db() -> None:
    """Test helper: drop engine + session factory."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None


def _redacted_url() -> str:
    url = _resolve_url()
    if "@" not in url:
        return url
    scheme, rest = url.split("://", 1)
    creds, host = rest.split("@", 1)
    return f"{scheme}://***@{host}"
