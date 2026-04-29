"""OpenTelemetry helper: enrich the active span with GenAI-spec attributes.

Uses opentelemetry.trace.get_current_span() so callers don't need to thread a
tracer through the codebase. If OTel isn't initialized, get_current_span()
returns a no-op span and these calls are cheap and safe.
"""

from __future__ import annotations

from typing import Any

try:
    from opentelemetry import trace as _trace

    _HAVE_OTEL = True
except ImportError:  # pragma: no cover
    _trace = None  # type: ignore[assignment]
    _HAVE_OTEL = False


def set_llm_span_attributes(
    *,
    tenant_id: str,
    requested_model: str,
    provider: str,
    upstream_model: str,
    prompt_tokens: int,
    completion_tokens: int,
    cost_usd: float | None,
    cache: str,
    fallback_used: bool,
) -> None:
    if not _HAVE_OTEL:
        return
    span = _trace.get_current_span()
    if span is None or not span.is_recording():
        return
    attrs: dict[str, Any] = {
        # Following opentelemetry-semantic-conventions GenAI naming
        "gen_ai.system": provider,
        "gen_ai.request.model": requested_model,
        "gen_ai.response.model": upstream_model,
        "gen_ai.usage.input_tokens": prompt_tokens,
        "gen_ai.usage.output_tokens": completion_tokens,
        # Gateway-specific
        "llm_gateway.tenant_id": tenant_id,
        "llm_gateway.cache": cache,
        "llm_gateway.fallback_used": fallback_used,
    }
    if cost_usd is not None:
        attrs["llm_gateway.cost_usd"] = cost_usd
    for k, v in attrs.items():
        try:
            span.set_attribute(k, v)
        except Exception:  # pragma: no cover - never fail user request on telemetry
            pass
