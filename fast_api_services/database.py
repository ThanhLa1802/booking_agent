from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from .config import get_settings

_engine = None
_session_factory = None


def _get_engine():
    global _engine, _session_factory
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.database_url,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
        )
        _session_factory = async_sessionmaker(
            _engine, expire_on_commit=False, class_=AsyncSession
        )
    return _engine, _session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    _, session_factory = _get_engine()
    async with session_factory() as session:
        yield session


def get_session_factory():
    """Return the async session factory for use outside of FastAPI dependency injection."""
    _, session_factory = _get_engine()
    return session_factory
