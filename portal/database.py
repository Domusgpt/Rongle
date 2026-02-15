"""
Database engine and session management.

Uses SQLAlchemy 2.0 async API with aiosqlite for MVP.
Swap DATABASE_URL to ``postgresql+asyncpg://...`` for production.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from .config import settings

engine_args = {
    "echo": settings.DEBUG,
}

if "sqlite" in settings.DATABASE_URL:
    engine_args["connect_args"] = {"check_same_thread": False}
else:
    # Postgres Production Tuning
    # - pool_size: number of permanent connections
    # - max_overflow: how many new connections to create above pool_size
    # - pool_timeout: seconds to wait for a connection before raising timeout
    engine_args.update({
        "pool_size": 20,
        "max_overflow": 10,
        "pool_timeout": 30,
        "pool_pre_ping": True,  # Detect disconnected connections
    })

engine = create_async_engine(
    settings.DATABASE_URL,
    **engine_args
)

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""
    pass


async def init_db() -> None:
    """Create all tables (idempotent)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncSession:  # type: ignore[misc]
    """FastAPI dependency that yields a database session."""
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()
