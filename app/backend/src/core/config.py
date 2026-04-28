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
    app_name: str = "CodeGuardian AI"
    app_version: str = "0.1.0"
    app_env: str = "development"
    app_debug: bool = True
    log_level: str = "DEBUG"

    # Server
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000

    # AWS Configuration
    aws_region: str = "us-east-1"
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    aws_profile: str | None = None

    # Bedrock
    bedrock_model_id: str = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
    bedrock_max_tokens: int = 4096
    bedrock_temperature: float = 0.1  # Low temp for consistent security analysis

    # CORS
    cors_origins: list[str] = ["http://localhost:8501", "http://localhost:3000"]

    @property
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.app_env.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
