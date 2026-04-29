"""Per-provider, per-model pricing.

Token prices are USD per 1M tokens. Update as providers change pricing.
Used by the usage middleware to compute cost_usd per request.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelPricing:
    input_per_million: float
    output_per_million: float

    def cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        return (
            prompt_tokens * self.input_per_million / 1_000_000
            + completion_tokens * self.output_per_million / 1_000_000
        )


# Conservative defaults. Real values should be loaded from config in production
# so price changes don't require a code deploy.
PRICING: dict[str, ModelPricing] = {
    # Anthropic Claude (Bedrock pricing as of 2026-Q1)
    "anthropic.claude-sonnet-4-5-20250929-v1:0": ModelPricing(3.00, 15.00),
    "us.anthropic.claude-sonnet-4-5-20250929-v1:0": ModelPricing(3.00, 15.00),
    "anthropic.claude-haiku-4-5": ModelPricing(0.80, 4.00),
    # OpenAI
    "gpt-4o": ModelPricing(2.50, 10.00),
    "gpt-4o-mini": ModelPricing(0.15, 0.60),
    "gpt-4.1": ModelPricing(2.00, 8.00),
    "gpt-4.1-mini": ModelPricing(0.40, 1.60),
}


def estimate_cost(model_id: str, prompt_tokens: int, completion_tokens: int) -> float | None:
    pricing = PRICING.get(model_id)
    if pricing is None:
        # Try to match by family prefix (e.g., us.anthropic.claude-... -> anthropic.claude-...)
        for known, p in PRICING.items():
            if model_id.endswith(known) or known.endswith(model_id):
                pricing = p
                break
    if pricing is None:
        return None
    return round(pricing.cost(prompt_tokens, completion_tokens), 6)
