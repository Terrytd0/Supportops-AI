"""Application settings, sourced from environment variables (12-factor config).

TODO: Expand with per-domain settings (LLM provider keys, agent timeouts,
policy thresholds, rate limits) as those subsystems are implemented.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "SupportOps AI"
    environment: str = "local"
    debug: bool = False

    # TODO: replace defaults with required (no-default) fields once deployment
    # environments are defined; defaults are provided only so the app boots
    # locally without a .env file during scaffolding.
    database_url: str = "postgresql+asyncpg://supportops:supportops@localhost:5432/supportops_ai"

    # --- Redis (ephemeral infra only -- never the system of record; see
    # docs/architecture.md and backend/core/README.md) ---
    redis_url: str = "redis://localhost:6379/0"
    # Short on purpose: callers must fail fast and degrade gracefully rather
    # than block a request while a down Redis times out slowly.
    redis_connect_timeout_seconds: float = 0.5
    redis_idempotency_ttl_seconds: int = 86400
    redis_checkpoint_ttl_seconds: int = 3600
    redis_classification_cache_ttl_seconds: int = 3600
    redis_knowledge_cache_ttl_seconds: int = 900

    # --- Auth (JWT/OAuth2) ---
    # TODO: remove insecure default before any non-local deployment.
    jwt_secret_key: str = "CHANGE_ME"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30

    # --- LLM ---
    llm_provider: str = "openai"
    openai_api_key: str = ""
    llm_model: str = "gpt-5.4-mini"
    llm_temperature: float = 0.3
    llm_request_timeout_seconds: int = 30


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
