"""Top-level routing engine.

Responsibilities:
  - Resolve the request's model field into an ordered provider chain
  - Execute the chain, advancing on retryable failures
  - Update circuit breakers
  - Return a normalized OpenAI-shaped response with gateway metadata
"""

from __future__ import annotations

import time
import uuid

import structlog

from src.api.schemas import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    Choice,
    ChoiceMessage,
    GatewayMeta,
    Usage,
)
from src.providers.base import ProviderError
from src.providers.pricing import estimate_cost
from src.providers.registry import ProviderRegistry, get_registry
from src.routing.policies import resolve_chain

logger = structlog.get_logger(__name__)


class NoProviderAvailable(Exception):
    pass


class AllProvidersFailed(Exception):
    def __init__(self, attempts: list[str], last_error: Exception):
        super().__init__(f"all providers failed: {attempts}; last_error={last_error}")
        self.attempts = attempts
        self.last_error = last_error


async def route(
    request: ChatCompletionRequest,
    *,
    registry: ProviderRegistry | None = None,
    fallback_enabled: bool = True,
) -> ChatCompletionResponse:
    reg = registry or get_registry()
    chain = resolve_chain(request.model, reg, fallback_enabled=fallback_enabled)

    if not chain:
        raise NoProviderAvailable(
            f"no provider available for model={request.model!r}"
        )

    attempts: list[str] = []
    last_error: Exception | None = None
    started = time.perf_counter()

    for provider_name, upstream_model in chain:
        entry = reg.get(provider_name)
        if entry is None or not entry.breaker.allow():
            continue
        attempts.append(f"{provider_name}:{upstream_model}")
        attempt_started = time.perf_counter()
        try:
            result = await entry.provider.chat(request, upstream_model=upstream_model)
        except ProviderError as e:
            entry.breaker.record_failure()
            last_error = e
            logger.warning(
                "route.attempt_failed",
                provider=provider_name,
                model=upstream_model,
                retryable=e.retryable,
                error=str(e),
            )
            if not e.retryable:
                # Non-retryable: stop trying further providers (likely a client bug)
                raise AllProvidersFailed(attempts, e) from e
            continue
        except Exception as e:  # pragma: no cover - unexpected
            entry.breaker.record_failure()
            last_error = e
            logger.exception("route.attempt_unexpected", provider=provider_name)
            continue

        entry.breaker.record_success()
        latency_ms = round((time.perf_counter() - attempt_started) * 1000, 2)
        total_latency_ms = round((time.perf_counter() - started) * 1000, 2)
        cost = estimate_cost(result.model, result.prompt_tokens, result.completion_tokens)

        logger.info(
            "route.success",
            provider=provider_name,
            upstream_model=result.model,
            latency_ms=latency_ms,
            total_latency_ms=total_latency_ms,
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            cost_usd=cost,
            attempts=len(attempts),
        )

        return ChatCompletionResponse(
            id=f"chatcmpl-{uuid.uuid4().hex[:24]}",
            created=int(time.time()),
            model=result.model,
            choices=[
                Choice(
                    index=0,
                    message=ChoiceMessage(role="assistant", content=result.content),
                    finish_reason=result.finish_reason,
                )
            ],
            usage=Usage(
                prompt_tokens=result.prompt_tokens,
                completion_tokens=result.completion_tokens,
                total_tokens=result.total_tokens,
            ),
            gateway=GatewayMeta(
                provider=provider_name,
                upstream_model=result.model,
                latency_ms=total_latency_ms,
                cache="miss",
                fallback_used=len(attempts) > 1,
                attempts=attempts,
                cost_usd=cost,
            ),
        )

    raise AllProvidersFailed(attempts, last_error or RuntimeError("no providers tried"))
