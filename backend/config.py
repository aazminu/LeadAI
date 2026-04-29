# backend/config.py

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """
    Central configuration for LeadOS.
    All values loaded from .env file.
    Pydantic validates types and raises clear errors
    on startup if required variables are missing.
    """

    # ─── App ───────────────────────────────────────────────
    app_name: str = "LeadOS"
    debug: bool = False
    cors_origins: list[str] = ["http://localhost:5173"]

    # ─── Database ──────────────────────────────────────────
    database_url: str

    # ─── LLM ───────────────────────────────────────────────
    litellm_model: str = "anthropic/claude-sonnet-4-5"
    llm_max_tokens: int = 1000
    llm_temperature: float = 0.3

    # ─── Anthropic ─────────────────────────────────────────
    anthropic_api_key: str

    # ─── Enrichment APIs ───────────────────────────────────
    news_api_key: str
    census_api_key: str
    fred_api_key: str
    walkscore_api_key: str
    hud_api_token: str = ""
    # ─── Exa AI ────────────────────────────────────────────
    exa_api_key: str = ""



    # ─── Adzuna (values agent — job postings signal) ───────
    adzuna_app_id: str
    adzuna_app_key: str

    # ─── Agent Behavior ────────────────────────────────────
    agent_timeout: int = 30
    agent_max_retries: int = 2

    # ─── Scheduler ─────────────────────────────────────────
    scheduler_hour: int = 9
    scheduler_minute: int = 0

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()