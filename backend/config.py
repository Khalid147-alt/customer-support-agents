"""Application settings loaded from environment / .env via pydantic-settings."""
import os
from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_chroma_dir() -> str:
    """Use /tmp on HuggingFace (read-only filesystem outside /tmp); ./chroma_db locally."""
    if os.environ.get("ENVIRONMENT", "").lower() == "production":
        return "/tmp/chroma_db"
    return "./chroma_db"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    gemini_api_key: str = Field(..., description="Google AI Studio API key for Gemini 2.5")
    # database_url is optional in SQLite mode (HuggingFace Spaces).
    database_url: str | None = Field(
        default=None,
        description="Postgres DSN, e.g. postgresql://admin:password@localhost:5432/support_agent",
    )
    use_sqlite: bool = Field(
        default=False,
        description="When true, use the aiosqlite backend instead of asyncpg/Postgres.",
    )
    chroma_dir: str = Field(
        default_factory=_default_chroma_dir,
        description="ChromaDB persistence directory. Defaults to /tmp/chroma_db in production.",
    )
    redis_url: str | None = Field(
        default=None,
        description="Optional Redis URL for session memory; falls back to in-memory dict if unset.",
    )
    environment: Literal["development", "staging", "production"] = "development"

    gemini_model: str = Field(
        default="gemini-2.5-flash",
        description="Gemini model identifier used for router and respond nodes.",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings accessor. Single instance per process."""
    return Settings()  # type: ignore[call-arg]
