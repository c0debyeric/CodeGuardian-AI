"""Application configuration using pydantic-settings."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "LLM Gateway"
    app_version: str = "0.1.0"
    app_env: str = "development"
    app_debug: bool = True
    log_level: str = "INFO"

    # Server
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000

    # AWS / Bedrock
    aws_region: str = "us-east-1"
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    aws_profile: str | None = None
    bedrock_enabled: bool = True

    # OpenAI
    openai_enabled: bool = False
    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"

    # Anthropic (direct, non-Bedrock)
    anthropic_enabled: bool = False
    anthropic_api_key: str | None = None

    # Routing
    default_model: str = "auto"
    fallback_enabled: bool = True
    request_timeout_seconds: float = 60.0

    # Circuit breaker
    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_recovery_seconds: int = 30

    # Storage (Phase 2+)
    redis_url: str | None = None
    database_url: str | None = None

    # Auth (Phase 2)
    auth_enabled: bool = False
    admin_api_key: str | None = None

    # Guardrails (Phase 4)
    guardrails_enabled: bool = False
    guardrails_redact_pii: bool = True

    # Cache (Phase 4)
    semantic_cache_enabled: bool = False
    semantic_cache_threshold: float = 0.95
    semantic_cache_ttl_seconds: int = 3600
    # "exact"   = sha256(prompt)             — fast, zero false positives
    # "semantic"= embedding + cosine NN     — paraphrase-aware, higher hit rate
    semantic_cache_mode: str = "exact"
    semantic_cache_max_entries: int = 1000

    # CORS
    cors_origins: list[str] = [
        "http://localhost:8501",
        "http://localhost:3000",
    ]

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
