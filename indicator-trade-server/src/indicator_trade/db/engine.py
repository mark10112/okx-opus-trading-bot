"""AsyncEngine + session factory for PostgreSQL."""

from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine


def create_db_engine(database_url: str) -> AsyncEngine:
    """Create async SQLAlchemy engine with asyncpg."""
    return create_async_engine(
        database_url,
        echo=False,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker:
    """Create async session factory."""
    return async_sessionmaker(engine, expire_on_commit=False)
