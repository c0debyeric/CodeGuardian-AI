"""LLM-specific Prometheus metrics + OTel span attributes.

Following emerging conventions from OpenLLMetry / OpenTelemetry GenAI semantic
conventions (gen_ai.* attributes). These metric names are scrape-compatible
with the Grafana dashboard shipped in argocd/dashboards/.

Why these specifically:
  - llm_requests_total: rate by tenant/model/provider — the headline chart
  - llm_request_duration_seconds: P50/P95/P99 latency for SLOs
  - llm_tokens_total: tokens in/out by model — drives the cost dashboard
  - llm_cost_usd_total: USD spend, computed from usage table pricing
  - llm_cache_events_total: hit vs miss vs bypass — proves cache value
  - llm_guardrail_events_total: PII detections by type — compliance audit trail
  - llm_provider_failures_total: by provider+reason — alerting target
"""

from __future__ import annotations

from prometheus_client import Counter, Histogram

LATENCY_BUCKETS = (
    0.05,
    0.1,
    0.25,
    0.5,
    1.0,
    2.0,
    5.0,
    10.0,
    20.0,
    30.0,
    60.0,
)


REQUESTS = Counter(
    "llm_requests_total",
    "Total LLM completion requests handled by the gateway.",
    ("tenant", "requested_model", "provider", "upstream_model", "status"),
)

DURATION = Histogram(
    "llm_request_duration_seconds",
    "End-to-end LLM request latency (seconds).",
    ("tenant", "provider", "upstream_model"),
    buckets=LATENCY_BUCKETS,
)

TOKENS = Counter(
    "llm_tokens_total",
    "Tokens consumed, labeled by direction.",
    ("tenant", "provider", "upstream_model", "direction"),  # direction in {prompt, completion}
)

COST = Counter(
    "llm_cost_usd_total",
    "Estimated USD cost of completions.",
    ("tenant", "provider", "upstream_model"),
)

CACHE_EVENTS = Counter(
    "llm_cache_events_total",
    "Semantic cache events.",
    ("tenant", "event"),  # event in {hit, miss, bypass}
)

GUARDRAIL_EVENTS = Counter(
    "llm_guardrail_events_total",
    "Guardrail detections (e.g., PII redactions).",
    ("tenant", "type"),
)

PROVIDER_FAILURES = Counter(
    "llm_provider_failures_total",
    "Upstream provider failures.",
    ("provider", "reason"),
)


def record_completion(
    *,
    tenant_id: str,
    requested_model: str,
    provider: str,
    upstream_model: str,
    status: str,
    duration_seconds: float,
    prompt_tokens: int,
    completion_tokens: int,
    cost_usd: float | None,
    cache_event: str,
    fallback_used: bool,
) -> None:
    """One-stop function so route handlers don't import the whole module."""
    REQUESTS.labels(tenant_id, requested_model, provider, upstream_model, status).inc()
    DURATION.labels(tenant_id, provider, upstream_model).observe(duration_seconds)
    if prompt_tokens:
        TOKENS.labels(tenant_id, provider, upstream_model, "prompt").inc(prompt_tokens)
    if completion_tokens:
        TOKENS.labels(tenant_id, provider, upstream_model, "completion").inc(completion_tokens)
    if cost_usd:
        COST.labels(tenant_id, provider, upstream_model).inc(cost_usd)
    CACHE_EVENTS.labels(tenant_id, cache_event).inc()
    if fallback_used:
        # Reuse failures counter with a synthetic "fallback_used" reason
        PROVIDER_FAILURES.labels(provider, "fallback_used").inc(0)  # no-op label registration
