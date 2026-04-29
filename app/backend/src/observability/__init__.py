"""Observability package: Prometheus metrics + OTel helpers."""

from src.observability.metrics import (
    CACHE_EVENTS,
    COST,
    DURATION,
    GUARDRAIL_EVENTS,
    PROVIDER_FAILURES,
    REQUESTS,
    TOKENS,
    record_completion,
)
from src.observability.tracing import set_llm_span_attributes

__all__ = [
    "CACHE_EVENTS",
    "COST",
    "DURATION",
    "GUARDRAIL_EVENTS",
    "PROVIDER_FAILURES",
    "REQUESTS",
    "TOKENS",
    "record_completion",
    "set_llm_span_attributes",
]
