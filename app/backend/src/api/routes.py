"""HTTP API routes (OpenAI-compatible)."""

from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from src.api.schemas import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    HealthResponse,
    ModelInfo,
    ModelList,
    ProviderHealth,
)
from src.auth import Tenant, get_current_tenant
from src.auth.ratelimit import get_rate_limiter
from src.core.config import get_settings
from src.middleware.cache import SemanticCache, cache_key, get_cache, prompt_text
from src.middleware.guardrails import apply_to_messages
from src.observability import GUARDRAIL_EVENTS, record_completion, set_llm_span_attributes
from src.providers.registry import get_registry
from src.routing.router import (
    AllProvidersFailed,
    NoProviderAvailable,
    route,
)
from src.usage.models import UsageRecord
from src.usage.repository import get_usage_repo

logger = structlog.get_logger(__name__)

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["meta"])
async def health() -> HealthResponse:
    settings = get_settings()
    reg = get_registry()
    providers = []
    for entry in reg.all():
        ok = await entry.provider.health()
        providers.append(
            ProviderHealth(name=entry.provider.name, healthy=ok, circuit=entry.breaker.state)
        )
    overall = "healthy" if any(p.healthy for p in providers) else "degraded"
    return HealthResponse(status=overall, version=settings.app_version, providers=providers)


@router.get("/v1/models", response_model=ModelList, tags=["openai"])
async def list_models(
    tenant: Tenant = Depends(get_current_tenant),
) -> ModelList:
    reg = get_registry()
    now = int(time.time())
    data = [
        ModelInfo(id=m, created=now)
        for m in reg.list_all_models()
        if tenant.model_allowed(m)
    ]
    for alias in ("auto", "cheapest", "fastest"):
        data.append(ModelInfo(id=alias, created=now, owned_by="llm-gateway-alias"))
    return ModelList(data=data)


@router.post("/v1/chat/completions", tags=["openai"])
async def chat_completions(
    body: ChatCompletionRequest,
    request: Request,
    tenant: Tenant = Depends(get_current_tenant),
):
    """OpenAI-compatible chat completions.

    Returns either a `ChatCompletionResponse` (when `stream=false`) or a
    `text/event-stream` of OpenAI-shaped delta chunks (when `stream=true`).
    """
    settings = get_settings()

    if not tenant.model_allowed(body.model):
        raise HTTPException(
            status_code=403,
            detail=f"tenant {tenant.id!r} not allowed to use model {body.model!r}",
        )

    # Apply guardrails (PII redaction). Mutates messages before they reach providers.
    pii_detected: list[str] = []
    if settings.guardrails_enabled:
        new_msgs, pii_detected = apply_to_messages(
            body.messages, redact=settings.guardrails_redact_pii
        )
        body = body.model_copy(update={"messages": new_msgs})
        if pii_detected:
            logger.info("guardrails.redacted", tenant=tenant.id, types=pii_detected)
            for t in pii_detected:
                GUARDRAIL_EVENTS.labels(tenant.id, t).inc()

    # Semantic cache lookup (post-guardrails so we cache the *clean* prompt).
    # Cache is bypassed for streaming requests in this MVP — caching SSE
    # streams cleanly is its own design problem.
    ck: str | None = None
    cached_response = None
    cache_backend = get_cache() if settings.semantic_cache_enabled else None
    semantic_mode = (
        settings.semantic_cache_enabled
        and settings.semantic_cache_mode == "semantic"
        and isinstance(cache_backend, SemanticCache)
    )

    if cache_backend is not None and not body.stream:
        ck = cache_key(body)
        if semantic_mode:
            assert isinstance(cache_backend, SemanticCache)
            hit = await cache_backend.get_semantic(
                namespace=body.model, text=prompt_text(body)
            )
            if hit is not None:
                cached_response, similarity = hit
                logger.info(
                    "cache.semantic_hit", tenant=tenant.id, similarity=round(similarity, 4)
                )
        else:
            cached_response = await cache_backend.get(ck)
            if cached_response is not None:
                logger.info("cache.hit", tenant=tenant.id, key=ck[:12])

        if cached_response is not None:
            cached_response = cached_response.model_copy(deep=True)
            if cached_response.gateway is not None:
                cached_response.gateway = cached_response.gateway.model_copy(
                    update={"cache": "hit", "fallback_used": False, "attempts": ["cache"]}
                )
            meta = cached_response.gateway
            if meta is not None:
                record_completion(
                    tenant_id=tenant.id,
                    requested_model=body.model,
                    provider=meta.provider,
                    upstream_model=meta.upstream_model,
                    status="200",
                    duration_seconds=0.0,
                    prompt_tokens=0,
                    completion_tokens=0,
                    cost_usd=0.0,
                    cache_event="hit",
                    fallback_used=False,
                )
            return cached_response

    try:
        response = await route(body, fallback_enabled=settings.fallback_enabled)
    except NoProviderAvailable as e:
        logger.warning("api.no_provider", model=body.model)
        raise HTTPException(status_code=503, detail=str(e)) from e
    except AllProvidersFailed as e:
        logger.warning("api.all_providers_failed", attempts=e.attempts)
        raise HTTPException(
            status_code=502, detail={"message": str(e), "attempts": e.attempts}
        ) from e

    # Store in cache (best-effort) — only for non-streaming responses
    if cache_backend is not None and ck is not None:
        try:
            if semantic_mode:
                assert isinstance(cache_backend, SemanticCache)
                await cache_backend.set_semantic(
                    namespace=body.model,
                    text=prompt_text(body),
                    value=response,
                    ttl=settings.semantic_cache_ttl_seconds,
                )
            else:
                await cache_backend.set(
                    ck, response, ttl=settings.semantic_cache_ttl_seconds
                )
        except Exception as e:  # pragma: no cover
            logger.warning("cache.set_failed", error=str(e))

    await _record_completion(tenant, body, response)

    if body.stream:
        return StreamingResponse(
            _sse_stream(response),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
    return response


async def _record_completion(
    tenant: Tenant, body: ChatCompletionRequest, response: ChatCompletionResponse
) -> None:
    """Persist usage, charge TPM, update budget cache, emit metrics + OTel attrs.

    Shared by the non-streaming and streaming code paths. Never raises — a
    bookkeeping failure must not corrupt a successful upstream call.
    """
    await get_rate_limiter().record_tokens(tenant.id, response.usage.total_tokens)

    meta = response.gateway
    if meta is None:
        return

    try:
        await get_usage_repo().insert(
            UsageRecord(
                request_id=response.id,
                tenant_id=tenant.id,
                requested_model=body.model,
                upstream_provider=meta.provider,
                upstream_model=meta.upstream_model,
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens,
                cost_usd=meta.cost_usd,
                latency_ms=meta.latency_ms,
                cache_status=meta.cache,
                fallback_used=meta.fallback_used,
            )
        )
    except Exception as e:  # pragma: no cover
        logger.warning("usage.insert_failed", error=str(e))

    if meta.cost_usd:
        from src.auth.budget import record_spend

        record_spend(tenant.id, meta.cost_usd)

    record_completion(
        tenant_id=tenant.id,
        requested_model=body.model,
        provider=meta.provider,
        upstream_model=meta.upstream_model,
        status="200",
        duration_seconds=meta.latency_ms / 1000.0,
        prompt_tokens=response.usage.prompt_tokens,
        completion_tokens=response.usage.completion_tokens,
        cost_usd=meta.cost_usd,
        cache_event=meta.cache,
        fallback_used=meta.fallback_used,
    )
    set_llm_span_attributes(
        tenant_id=tenant.id,
        requested_model=body.model,
        provider=meta.provider,
        upstream_model=meta.upstream_model,
        prompt_tokens=response.usage.prompt_tokens,
        completion_tokens=response.usage.completion_tokens,
        cost_usd=meta.cost_usd,
        cache=meta.cache,
        fallback_used=meta.fallback_used,
    )


def _sse_chunk(payload: dict) -> bytes:
    """Format a single SSE event in OpenAI's chunked-completion shape."""
    return f"data: {json.dumps(payload, separators=(',', ':'))}\n\n".encode()


async def _sse_stream(response: ChatCompletionResponse) -> AsyncIterator[bytes]:
    """Yield OpenAI-compatible SSE deltas for an already-completed response.

    NOTE on design: this MVP wraps a buffered upstream response and chunks it
    word-by-word for the client. That gets `openai-python` (and any other SDK
    that expects `text/event-stream`) working without touching providers, and
    keeps the contract testable end-to-end. Real upstream streaming (Bedrock
    `invoke_model_with_response_stream`, OpenAI `stream=true`) is a per-provider
    follow-up — the wire shape stays identical, so clients won't notice.
    """
    choice = response.choices[0] if response.choices else None
    content = choice.message.content if choice and choice.message else ""
    base = {
        "id": response.id,
        "object": "chat.completion.chunk",
        "created": response.created,
        "model": response.model,
    }

    # First chunk announces the assistant role.
    yield _sse_chunk({**base, "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}]})

    # Stream content in word-sized deltas. Empty content still produces a valid
    # (single, role-only) stream that terminates correctly.
    if content:
        # Preserve whitespace — split keeping separators so spaces aren't lost.
        parts: list[str] = []
        buf = ""
        for ch in content:
            buf += ch
            if ch.isspace():
                parts.append(buf)
                buf = ""
        if buf:
            parts.append(buf)
        for part in parts:
            yield _sse_chunk(
                {**base, "choices": [{"index": 0, "delta": {"content": part}, "finish_reason": None}]}
            )

    # Final chunk: empty delta + finish_reason, then the OpenAI [DONE] sentinel.
    finish = choice.finish_reason if choice else "stop"
    yield _sse_chunk({**base, "choices": [{"index": 0, "delta": {}, "finish_reason": finish}]})
    yield b"data: [DONE]\n\n"

