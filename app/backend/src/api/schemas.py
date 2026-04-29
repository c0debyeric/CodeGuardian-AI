"""OpenAI-compatible request/response schemas.

By matching OpenAI's wire format, any client library (openai-python, langchain,
llamaindex, curl examples from docs) works against this gateway with only a
base_url change. This is the primary onboarding lever for app teams.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


# ---------- Chat Completions (OpenAI-compatible) ----------


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str | list[dict[str, Any]]
    name: str | None = None
    tool_call_id: str | None = None


class ChatCompletionRequest(BaseModel):
    """OpenAI /v1/chat/completions request body.

    `model` may be a concrete provider model id (e.g. "gpt-4o-mini",
    "anthropic.claude-sonnet-4-5") or a routing alias like "auto",
    "cheapest", "fastest".
    """

    model: str
    messages: list[ChatMessage]
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, gt=0)
    top_p: float | None = Field(default=None, ge=0.0, le=1.0)
    stream: bool = False
    stop: str | list[str] | None = None
    user: str | None = None  # caller-supplied tenant/user identifier
    metadata: dict[str, Any] | None = None  # gateway routing hints


class Usage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChoiceMessage(BaseModel):
    role: str = "assistant"
    content: str | None = None


class Choice(BaseModel):
    index: int = 0
    message: ChoiceMessage
    finish_reason: str | None = "stop"


class GatewayMeta(BaseModel):
    """Non-standard response field describing how the gateway handled the call."""

    provider: str
    upstream_model: str
    latency_ms: float
    cache: Literal["hit", "miss", "bypass"] = "miss"
    fallback_used: bool = False
    attempts: list[str] = Field(default_factory=list)
    cost_usd: float | None = None


class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: list[Choice]
    usage: Usage
    gateway: GatewayMeta | None = None  # gateway extension


# ---------- Models endpoint ----------


class ModelInfo(BaseModel):
    id: str
    object: str = "model"
    created: int = 0
    owned_by: str = "llm-gateway"


class ModelList(BaseModel):
    object: str = "list"
    data: list[ModelInfo]


# ---------- Errors (OpenAI-compatible) ----------


class ErrorDetail(BaseModel):
    message: str
    type: str = "gateway_error"
    code: str | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail


# ---------- Health ----------


class ProviderHealth(BaseModel):
    name: str
    healthy: bool
    circuit: Literal["closed", "open", "half_open"] = "closed"


class HealthResponse(BaseModel):
    status: str
    version: str
    providers: list[ProviderHealth]
