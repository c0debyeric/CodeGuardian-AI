"""Tenant / API key models.

A "tenant" is the unit we meter and bill against — typically a team or
application. Each tenant has one or more API keys. Tenants have:
  - rate limits (requests per minute, tokens per minute)
  - allowlist of models (None = all)
  - monthly budget (USD; None = unlimited)
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Tenant:
    id: str  # short id, e.g. "team-marketing"
    name: str
    rpm_limit: int = 60  # requests per minute
    tpm_limit: int = 100_000  # tokens per minute
    monthly_budget_usd: float | None = None
    allowed_models: list[str] | None = None  # None = all
    metadata: dict = field(default_factory=dict)

    def model_allowed(self, model_id: str) -> bool:
        if self.allowed_models is None:
            return True
        return model_id in self.allowed_models or model_id in {"auto", "cheapest", "fastest"}
