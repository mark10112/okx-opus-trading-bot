"""AsyncEngine + session factory for PostgreSQL."""

from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine


def create_db_engine(
    database_url: str,
    pool_size: int = 10,
    max_overflow: int = 20,
    pool_recycle: int = 1800,
    pool_timeout: int = 30,
) -> AsyncEngine:
    """Create async SQLAlchemy engine with asyncpg."""
    return create_async_engine(
        database_url,
        echo=False,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_pre_ping=True,
        pool_recycle=pool_recycle,
        pool_timeout=pool_timeout,
        pool_use_lifo=True,
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker:
    """Create async session factory."""
    return async_sessionmaker(engine, expire_on_commit=False)
