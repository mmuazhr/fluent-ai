from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings

# Resolve .env relative to this file so CWD doesn't matter
_ENV_FILE = str(Path(__file__).resolve().parent.parent / ".env")


class Settings(BaseSettings):
    # Gemini API (Free Tier via Google AI Studio)
    gemini_api_key: str = ""

    # LLM Config
    gemini_model_name: str = "gemini-flash-lite-latest"
    gemini_max_tokens: int = 1024
    gemini_temperature: float = 0.85

    # Database
    database_url: str = ""

    # App
    app_name: str = "Balqis"
    debug: bool = False
    # cors_origins: set to specific origins in production; ["*"] is open for local dev
    cors_origins: list[str] = ["*"]

    # Auth: when non-empty, all /api routes require Bearer <token>
    app_access_token: str = ""

    # Memory
    context_window_turns: int = 20
    analytics_flush_every_n: int = 3

    # Obsidian vault root (empty = disabled)
    vault_root: str = ""

    class Config:
        env_file = _ENV_FILE
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    return Settings()
