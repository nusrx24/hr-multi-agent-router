"""
Configuration module for the HR Multi-Agent Router.

Loads environment variables from .env into a typed Settings object
using pydantic-settings. All application configuration is centralized here.
"""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    groq_api_key: str = "gsk_placeholder"
    model_name: str = "llama-3.3-70b-versatile"

    database_url: str = "hr_engine.db"

    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = True

    confidence_threshold: float = 0.4
    """Requests with confidence below this value route to ClarificationAgent."""

    significance_threshold: float = 0.6
    """Memory entries with significance >= this value are stored as LTM."""

    max_stm_entries: int = 10
    """Maximum number of STM entries to keep per user."""

    llm_timeout: int = 30
    """Timeout in seconds for LLM API calls."""

    llm_max_retries: int = 2
    """Maximum number of retries for failed LLM calls."""


@lru_cache()
def get_settings() -> Settings:
    """
    Return a cached Settings instance.

    Uses lru_cache so the .env file is only read once during
    the application lifecycle.
    """
    return Settings()
