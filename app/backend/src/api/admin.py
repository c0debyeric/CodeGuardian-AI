"""Admin endpoints for tenant + API key management.

Protected by `X-Admin-Key` header matching settings.admin_api_key. Disabled
entirely if no admin key is configured.

These are intentionally minimal — a real product would back this with Postgres
and add audit logging. For the demo, an in-memory keystore is enough to show
the platform-team operator workflow.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field

from src.auth.keystore import get_keystore
from src.auth.models import Tenant
from src.core.config import get_settings
from src.usage.repository import get_usage_repo

router = APIRouter(prefix="/admin", tags=["admin"])


def _require_admin(x_admin_key: str | None = Header(default=None)) -> None:
    settings = get_settings()
    if not settings.admin_api_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="admin api disabled (no ADMIN_API_KEY configured)",
        )
    if x_admin_key != settings.admin_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid admin key"
        )


class CreateTenantRequest(BaseModel):
    id: str = Field(..., min_length=1, max_length=64)
    name: str
    rpm_limit: int = 60
    tpm_limit: int = 100_000
    monthly_budget_usd: float | None = None
    allowed_models: list[str] | None = None


class CreateKeyResponse(BaseModel):
    tenant_id: str
    api_key: str  # plaintext; shown ONCE — not retrievable later
    label: str
    warning: str = "store this key now; it cannot be retrieved again"


class TenantSummary(BaseModel):
    id: str
    name: str
    rpm_limit: int
    tpm_limit: int
    monthly_budget_usd: float | None


@router.post(
    "/tenants",
    response_model=CreateKeyResponse,
    dependencies=[Depends(_require_admin)],
    status_code=201,
)
async def create_tenant(req: CreateTenantRequest) -> CreateKeyResponse:
    tenant = Tenant(
        id=req.id,
        name=req.name,
        rpm_limit=req.rpm_limit,
        tpm_limit=req.tpm_limit,
        monthly_budget_usd=req.monthly_budget_usd,
        allowed_models=req.allowed_models,
    )
    plaintext = get_keystore().create_key(tenant)
    return CreateKeyResponse(tenant_id=tenant.id, api_key=plaintext, label="default")


@router.get(
    "/tenants",
    response_model=list[TenantSummary],
    dependencies=[Depends(_require_admin)],
)
async def list_tenants() -> list[TenantSummary]:
    return [
        TenantSummary(
            id=t.id,
            name=t.name,
            rpm_limit=t.rpm_limit,
            tpm_limit=t.tpm_limit,
            monthly_budget_usd=t.monthly_budget_usd,
        )
        for t in get_keystore().list_tenants()
    ]


class UsageSummaryItem(BaseModel):
    tenant_id: str
    requests: int
    total_tokens: int
    cost_usd: float


class ModelUsageItem(BaseModel):
    upstream_model: str
    requests: int
    cost_usd: float


@router.get(
    "/usage/by-tenant",
    response_model=list[UsageSummaryItem],
    dependencies=[Depends(_require_admin)],
)
async def usage_by_tenant() -> list[UsageSummaryItem]:
    rows = await get_usage_repo().usage_by_tenant()
    return [
        UsageSummaryItem(
            tenant_id=r.tenant_id,
            requests=r.requests,
            total_tokens=r.total_tokens,
            cost_usd=r.cost_usd,
        )
        for r in rows
    ]


@router.get(
    "/usage/by-model",
    response_model=list[ModelUsageItem],
    dependencies=[Depends(_require_admin)],
)
async def usage_by_model() -> list[ModelUsageItem]:
    rows = await get_usage_repo().usage_by_model()
    return [
        ModelUsageItem(upstream_model=m, requests=c, cost_usd=cost) for m, c, cost in rows
    ]


class RecentUsageItem(BaseModel):
    ts: datetime
    request_id: str
    tenant_id: str
    requested_model: str
    upstream_provider: str
    upstream_model: str
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float | None
    latency_ms: float
    cache_status: str
    fallback_used: bool


@router.get(
    "/usage/recent",
    response_model=list[RecentUsageItem],
    dependencies=[Depends(_require_admin)],
)
async def usage_recent(limit: int = 50) -> list[RecentUsageItem]:
    """Last N completions, newest first. Powers the admin live log table."""
    limit = max(1, min(limit, 500))
    rows = await get_usage_repo().recent(limit=limit)
    return [
        RecentUsageItem(
            ts=r.ts,
            request_id=r.request_id,
            tenant_id=r.tenant_id,
            requested_model=r.requested_model,
            upstream_provider=r.upstream_provider,
            upstream_model=r.upstream_model,
            prompt_tokens=r.prompt_tokens,
            completion_tokens=r.completion_tokens,
            cost_usd=r.cost_usd,
            latency_ms=r.latency_ms,
            cache_status=r.cache_status,
            fallback_used=r.fallback_used,
        )
        for r in rows
    ]


@router.delete(
    "/tenants/{tenant_id}/keys",
    dependencies=[Depends(_require_admin)],
)
async def revoke_tenant_keys(tenant_id: str) -> dict:
    """Revoke all API keys for a tenant. Idempotent."""
    n = get_keystore().revoke_tenant(tenant_id)
    return {"tenant_id": tenant_id, "revoked": n}
