"""
SKONGA Library API — Configuration
===================================
All sensitive values (tokens, DB URL) come from environment variables.
Nothing is hardcoded here. See .env.example for the full list.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ── Identity ──────────────────────────────────────────────────────────
    APP_NAME: str = "SKONGA Library API"
    VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"  # "production" on Render

    # ── Database ─────────────────────────────────────────────────────────
    # Full Postgres connection URL, e.g.
    # postgresql://user:password@host:5432/dbname
    DATABASE_URL: str

    # ── Security ──────────────────────────────────────────────────────────
    # SHA-256 hex hash of the bearer token held by SKONGA AI backend.
    # The token itself NEVER lives here — only its hash.
    # Generate: python3 -c "import hashlib; print(hashlib.sha256(b'YOUR_TOKEN').hexdigest())"
    SERVICE_TOKEN_HASH: str

    # ── Cache (Redis) ─────────────────────────────────────────────────────
    # Optional for Phase 1 — if not set, caching is skipped silently.
    REDIS_URL: str = ""
    CACHE_TTL_SUBJECTS: int = 1800   # seconds (30 min)
    CACHE_TTL_RAG: int = 300          # seconds (5 min)

    # ── Rate limiting ─────────────────────────────────────────────────────
    RATE_LIMIT_PER_MINUTE: int = 300

    # ── Logging ──────────────────────────────────────────────────────────
    LOG_LEVEL: str = "info"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton — imported everywhere as `settings`."""
    return Settings()


# Single importable instance
settings = get_settings()
