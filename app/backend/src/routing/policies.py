"""Model alias resolution + provider chain ordering.

Alias examples:
  - "auto"     : first available provider's default model
  - "cheapest" : pick the cheapest configured model
  - "fastest"  : pick the lowest-historical-latency model (placeholder: cheapest)
  - "<concrete>" : passthrough (e.g. "gpt-4o-mini")

Returns an ordered list of (provider_name, upstream_model) candidates. The
router tries them in order; on a retryable failure it advances to the next.
"""

from __future__ import annotations

from src.providers.pricing import PRICING
from src.providers.registry import ProviderRegistry

ALIASES = {"auto", "cheapest", "fastest"}


def resolve_chain(
    model: str, registry: ProviderRegistry, *, fallback_enabled: bool = True
) -> list[tuple[str, str]]:
    """Return an ordered list of (provider_name, upstream_model) attempts.

    For concrete model ids: only providers that serve that exact model are
    candidates. Fallback in this case means "another provider serving the same
    model" (rare today but useful for OpenAI-compatible mirrors and self-hosted).

    For aliases (auto/cheapest/fastest): the gateway is free to substitute
    across providers and models.
    """
    if model not in ALIASES:
        candidates = registry.for_model(model)
        chain: list[tuple[str, str]] = [(e.provider.name, model) for e in candidates]
        return chain if fallback_enabled else chain[:1]

    # Alias resolution
    if model in {"cheapest", "fastest"}:
        # Rank concrete models by input price (proxy for "fastest" too in Phase 1)
        candidates: list[tuple[float, str, str]] = []
        for entry in registry.all():
            if not entry.breaker.allow():
                continue
            for m in entry.provider.list_models():
                price = PRICING.get(m)
                if price is None:
                    continue
                candidates.append((price.input_per_million, entry.provider.name, m))
        candidates.sort(key=lambda x: x[0])
        chain = [(p, m) for _, p, m in candidates]
        return chain if fallback_enabled else chain[:1]

    # "auto": each available provider's default
    chain = []
    for entry in registry.all():
        if not entry.breaker.allow():
            continue
        default = getattr(entry.provider, "default_model", None) or (
            entry.provider.list_models()[0] if entry.provider.list_models() else None
        )
        if default:
            chain.append((entry.provider.name, default))
    return chain if fallback_enabled else chain[:1]
