"""Application settings.

This is the ONLY module allowed to read environment variables. Everything
else takes a `Settings` instance (or the `get_settings` dependency) instead
of touching `os.environ` / `os.getenv` directly.

Every field here corresponds 1:1 to a key in `.env.example`.
"""
from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Database (SQLAlchemy + asyncpg; see compose.yaml)
    database_url: str

    # LLM provider (langchain-openai; DESIGN §9)
    openai_api_key: str

    # Model routing — tier→model mapping lives in config, not code (DESIGN §9)
    model_understand: str
    model_respond: str

    # Intent classification threshold (DESIGN §3a)
    confidence_threshold: float

    # Global cap on rows returned by any template query (DESIGN §5)
    max_rows: int

    # Per-request LLM spend cap in USD (app/observability/cost.py)
    max_request_cost_usd: float = 0.50

    # structlog level
    log_level: str = "INFO"

    # Allowed CORS origins
    cors_origins: list[str] = []

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_cors_origins(cls, value: object) -> object:
        """Accept a comma-separated string from the environment as well as
        an already-parsed list (e.g. when constructed directly in tests)."""
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    """Singleton accessor, suitable for use as a FastAPI dependency."""
    return Settings()
