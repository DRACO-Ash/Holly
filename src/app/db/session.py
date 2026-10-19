"""The database engine and sessions.

One engine (and so one connection pool) per process, created on first use rather than at
import, and disposed at shutdown. Requests and the background loops share it.
"""

from collections.abc import AsyncIterator
from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import get_settings


@lru_cache(maxsize=1)
def get_engine() -> AsyncEngine:
    # A failed statement's error never carries its bound values, which can hold a password
    # hash or any other value a caller stores: the log gets the statement alone.
    return create_async_engine(
        get_settings().sqlalchemy_url(), pool_pre_ping=True, hide_parameters=True
    )


@lru_cache(maxsize=1)
def get_session_factory() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_engine(), expire_on_commit=False)


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: one session per request, closed when the response is done."""
    async with get_session_factory()() as session:
        yield session


async def dispose_engine() -> None:
    """Close every pooled connection, if an engine was ever created."""
    if get_engine.cache_info().currsize:
        await get_engine().dispose()
    get_session_factory.cache_clear()
    get_engine.cache_clear()
