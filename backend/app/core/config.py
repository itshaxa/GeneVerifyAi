"""Central application configuration.

All runtime configuration is read from environment variables (optionally via a
local ``.env`` file) so that no secrets are ever hardcoded. Secrets that do not
exist yet (JWT, Qwen API key) are intentionally NOT defined until the stage
that needs them.
"""

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed application settings loaded from the environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    #: Insecure development placeholder only. Production MUST set a strong,
    #: randomly generated JWT_SECRET_KEY via environment configuration.
    _INSECURE_DEV_SECRET = "dev-only-insecure-jwt-secret-CHANGE-ME-before-any-real-deployment"

    app_name: str = "GeneVerify AI API"
    app_env: str = Field(default="development", description="development | staging | production")
    app_version: str = "0.1.0"
    debug: bool = False

    # Versioned prefix under which all API routes are mounted.
    api_prefix: str = "/api/v1"

    # SQLite for the prototype; replaced by a managed database URL on Alibaba Cloud.
    database_url: str = "sqlite:///./geneverify.db"

    # Comma-separated allowlist of browser origins (frontend).
    cors_origins: str = "http://localhost:5173"

    log_level: str = "INFO"

    # --- Authentication (Step 3) ---
    jwt_secret_key: str = _INSECURE_DEV_SECRET
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = Field(default=60, ge=1, le=1440)

    # Demo admin credential for the hackathon seed command (synthetic only).
    demo_admin_username: str = "admin"
    demo_admin_password: str | None = None

    # --- Document upload (Step 6) ---
    # Local filesystem root for uploaded DNA/blood-test documents. Never
    # inside source control (gitignored) and never served statically.
    document_storage_path: str = "storage/documents"
    max_document_size_mb: int = Field(default=10, ge=1, le=100)

    # --- AI document intelligence (Step 7) ---
    # Provider selection: "qwen" for Alibaba Cloud Qwen, "mock" for the
    # deterministic development/testing provider (never allowed in production).
    ai_provider: str = "mock"
    # Qwen credentials/endpoint come from the environment only — never code.
    qwen_api_key: str | None = None
    qwen_model: str = "qwen-vl-max"
    qwen_base_url: str = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
    qwen_timeout_seconds: int = Field(default=60, ge=5, le=300)

    @field_validator("jwt_algorithm")
    @classmethod
    def _validate_jwt_algorithm(cls, value: str) -> str:
        if value not in {"HS256", "HS384", "HS512"}:
            raise ValueError("JWT_ALGORITHM must be an HMAC algorithm (HS256/HS384/HS512)")
        return value

    @field_validator("app_env")
    @classmethod
    def _validate_app_env(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"development", "staging", "production"}:
            raise ValueError("APP_ENV must be one of: development, staging, production")
        return normalized

    @field_validator("jwt_secret_key")
    @classmethod
    def _validate_jwt_secret(cls, value: str) -> str:
        if len(value.strip()) < 16:
            raise ValueError("JWT_SECRET_KEY must be at least 16 characters long")
        return value

    @field_validator("log_level")
    @classmethod
    def _validate_log_level(cls, value: str) -> str:
        normalized = value.strip().upper()
        if normalized not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError("LOG_LEVEL must be a standard Python logging level")
        return normalized

    @field_validator("ai_provider")
    @classmethod
    def _validate_ai_provider(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"qwen", "mock"}:
            raise ValueError("AI_PROVIDER must be one of: qwen, mock")
        return normalized

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def using_insecure_dev_jwt_secret(self) -> bool:
        return self.jwt_secret_key == self._INSECURE_DEV_SECRET


@lru_cache
def get_settings() -> Settings:
    """Return the cached settings singleton."""
    return Settings()
