"""Async SQLAlchemy engine, sessionmaker, and the `get_db` FastAPI dependency."""
from collections.abc import AsyncGenerator
from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import Settings, get_settings


@lru_cache
def get_engine() -> AsyncEngine:
    settings: Settings = get_settings()
    return create_async_engine(settings.database_url, pool_pre_ping=True)


@lru_cache
def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_engine(), expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        yield session


async def dispose_engine() -> None:
    """Called from the app lifespan on shutdown."""
    await get_engine().dispose()
