"""FastAPI dependencies for auth + rate limiting."""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.auth.budget import check_budget
from src.auth.keystore import get_keystore
from src.auth.models import Tenant
from src.auth.ratelimit import get_rate_limiter
from src.core.config import get_settings

_bearer = HTTPBearer(auto_error=False)


async def get_current_tenant(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> Tenant:
    """Resolve the calling tenant from the Authorization header.

    Raises 401 if auth is enabled and the key is missing/invalid.
    Also enforces RPM rate limit before the request is processed.
    """
    settings = get_settings()
    if not settings.auth_enabled:
        # Open mode: synthesize an anonymous tenant with permissive limits
        tenant = Tenant(id="anonymous", name="Anonymous", rpm_limit=10_000, tpm_limit=10_000_000)
        request.state.tenant = tenant
        return tenant

    if creds is None or not creds.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    record = get_keystore().lookup(creds.credentials)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid api key"
        )

    tenant = record.tenant
    request.state.tenant = tenant

    # RPM check (cheap, pre-call)
    limiter = get_rate_limiter()
    decision = await limiter.check_request(tenant.id, rpm_limit=tenant.rpm_limit)
    if not decision.allowed:
        headers = {}
        if decision.retry_after_seconds is not None:
            headers["Retry-After"] = str(int(decision.retry_after_seconds) + 1)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=decision.reason or "rate limit exceeded",
            headers=headers,
        )

    # TPM check (also pre-call: if last minute already over budget, refuse)
    tok_decision = await limiter.check_tokens(tenant.id, tpm_limit=tenant.tpm_limit)
    if not tok_decision.allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=tok_decision.reason or "token rate limit exceeded",
        )

    # Monthly USD budget check (no-op if tenant has no budget configured).
    # Returns 402 Payment Required so callers can distinguish budget exhaustion
    # from rate limiting (429) and from missing/invalid keys (401/403).
    budget_decision = await check_budget(tenant)
    if not budget_decision.allowed:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "message": budget_decision.reason or "monthly budget exceeded",
                "spent_usd": budget_decision.spent_usd,
                "budget_usd": budget_decision.budget_usd,
            },
        )

    return tenant


async def optional_tenant(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> Tenant | None:
    """Same as get_current_tenant but never raises. Used by /health."""
    try:
        return await get_current_tenant(request, creds)
    except HTTPException:
        return None
