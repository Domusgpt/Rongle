"""
Portal configuration — loaded from environment variables with sane defaults.
"""

from __future__ import annotations

import os
import secrets
from pathlib import Path


class PortalSettings:
    """Central configuration loaded from environment."""

    # -- Application --
    APP_NAME: str = "Rongle Portal"
    DEBUG: bool = os.getenv("RONGLE_DEBUG", "false").lower() == "true"

    # -- Database --
    # SQLite for MVP; swap to postgresql+asyncpg://... for production
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        f"sqlite+aiosqlite:///{Path(__file__).parent / 'rongle.db'}",
    )

    # -- Auth / JWT --
    JWT_SECRET: str = os.getenv("JWT_SECRET", secrets.token_urlsafe(48))
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MIN", "60"))
    REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "30"))

    # -- Encryption --
    # Fernet key for encrypting device API keys at rest.
    # Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    ENCRYPTION_KEY: str = os.getenv("ENCRYPTION_KEY", "")

    # -- LLM Proxy --
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    LLM_DEFAULT_MODEL: str = os.getenv("LLM_DEFAULT_MODEL", "gemini-2.0-flash")

    # -- Rate Limiting --
    RATE_LIMIT_PER_MINUTE: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))
    REDIS_URL: str | None = os.getenv("REDIS_URL", None)

    # -- CORS --
    CORS_ORIGINS: list[str] = os.getenv(
        "CORS_ORIGINS", "http://localhost:3000,http://localhost:5173"
    ).split(",")

    # -- Server --
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))


settings = PortalSettings()
