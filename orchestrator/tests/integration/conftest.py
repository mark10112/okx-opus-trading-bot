"""Shared fixtures for orchestrator integration tests.

Requires docker-compose.test.yml running:
  docker compose -f docker-compose.test.yml up -d
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest
import redis.asyncio as aioredis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

# Test infrastructure URLs (isolated ports from docker-compose.test.yml)
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:testpass@localhost:5433/trading_bot_test",
)
TEST_REDIS_URL = os.environ.get("TEST_REDIS_URL", "redis://localhost:6380")

ALEMBIC_DIR = Path(__file__).resolve().parents[2] / "alembic"
ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"


# ---------------------------------------------------------------------------
# Sync helpers (used in session-scoped fixtures to avoid event loop issues)
# ---------------------------------------------------------------------------


def _wait_for_postgres_sync(url: str, timeout: float = 30) -> None:
    """Block until PostgreSQL is reachable (sync, for session setup)."""
    import asyncpg

    dsn = url.replace("postgresql+asyncpg://", "postgresql://")
    deadline = time.monotonic() + timeout
    last_err: Exception | None = None
    while time.monotonic() < deadline:
        try:

            async def _check():
                conn = await asyncpg.connect(dsn)
                await conn.close()

            asyncio.run(_check())
            return
        except Exception as exc:
            last_err = exc
            time.sleep(0.5)
    raise TimeoutError(f"PostgreSQL not ready after {timeout}s: {last_err}")


def _wait_for_redis_sync(url: str, timeout: float = 30) -> None:
    """Block until Redis is reachable (sync, for session setup)."""
    import redis

    # redis://localhost:6380 -> host=localhost, port=6380
    r = redis.from_url(url)
    deadline = time.monotonic() + timeout
    last_err: Exception | None = None
    while time.monotonic() < deadline:
        try:
            r.ping()
            r.close()
            return
        except Exception as exc:
            last_err = exc
            time.sleep(0.5)
    raise TimeoutError(f"Redis not ready after {timeout}s: {last_err}")


def _run_alembic(cmd: str, revision: str = "head") -> None:
    """Run alembic command via subprocess (uses async env.py with asyncpg)."""
    env = os.environ.copy()
    env["DATABASE_URL"] = TEST_DATABASE_URL

    result = subprocess.run(
        [sys.executable, "-m", "alembic", cmd, revision],
        cwd=str(ALEMBIC_INI.parent),
        env=env,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"alembic {cmd} {revision} failed:\n{result.stderr}")


def _apply_migration_003() -> None:
    """Apply migration 003 (grafana_reader) with correct test DB name."""
    import asyncpg

    dsn = TEST_DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")

    async def _run():
        conn = await asyncpg.connect(dsn)
        try:
            await conn.execute(
                "DO $$ "
                "BEGIN "
                "  IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles "
                "    WHERE rolname = 'grafana_reader') THEN "
                "    CREATE USER grafana_reader WITH PASSWORD 'testpass'; "
                "  END IF; "
                "END $$"
            )
            await conn.execute(
                "GRANT CONNECT ON DATABASE trading_bot_test TO grafana_reader"
            )
            await conn.execute("GRANT USAGE ON SCHEMA public TO grafana_reader")
            await conn.execute(
                "GRANT SELECT ON ALL TABLES IN SCHEMA public TO grafana_reader"
            )
            await conn.execute(
                "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
                "GRANT SELECT ON TABLES TO grafana_reader"
            )
            await conn.execute("UPDATE alembic_version SET version_num = '003'")
        finally:
            await conn.close()

    asyncio.run(_run())


def _revert_migration_003() -> None:
    """Revert migration 003 (grafana_reader)."""
    import asyncpg

    dsn = TEST_DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")

    async def _run():
        conn = await asyncpg.connect(dsn)
        try:
            await conn.execute(
                "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
                "REVOKE SELECT ON TABLES FROM grafana_reader"
            )
            await conn.execute(
                "REVOKE ALL ON ALL TABLES IN SCHEMA public FROM grafana_reader"
            )
            await conn.execute("REVOKE USAGE ON SCHEMA public FROM grafana_reader")
            await conn.execute(
                "REVOKE CONNECT ON DATABASE trading_bot_test FROM grafana_reader"
            )
            await conn.execute("DROP USER IF EXISTS grafana_reader")
            await conn.execute("UPDATE alembic_version SET version_num = '002'")
        finally:
            await conn.close()

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Session-scoped: run once per test session (all synchronous to avoid
# event loop issues with pytest-asyncio on Windows)
# ---------------------------------------------------------------------------

_engine: AsyncEngine | None = None


@pytest.fixture(scope="session", autouse=True)
def _setup_test_infra():
    """Session setup: wait for infra, run migrations, create engine."""
    global _engine

    _wait_for_postgres_sync(TEST_DATABASE_URL)
    _wait_for_redis_sync(TEST_REDIS_URL)

    # Run alembic migrations 001-002
    _run_alembic("upgrade", "002")
    # Apply migration 003 manually (grafana_reader with correct DB name)
    _apply_migration_003()

    from sqlalchemy.pool import NullPool

    _engine = create_async_engine(TEST_DATABASE_URL, echo=False, poolclass=NullPool)

    yield

    # Teardown
    if _engine is not None:
        asyncio.run(_engine.dispose())
        _engine = None

    _revert_migration_003()
    _run_alembic("downgrade", "base")


# ---------------------------------------------------------------------------
# Function-scoped: fresh per test
# ---------------------------------------------------------------------------


@pytest.fixture
def db_engine() -> AsyncEngine:
    """Return the session-scoped async engine."""
    assert _engine is not None, "Test infra not initialized"
    return _engine


@pytest.fixture
def session_factory(db_engine) -> async_sessionmaker:
    """Async session factory bound to test DB."""
    return async_sessionmaker(db_engine, expire_on_commit=False)


@pytest.fixture
async def real_redis():
    """Real Redis client, FLUSHDB before each test."""
    client = aioredis.from_url(TEST_REDIS_URL, decode_responses=False)
    await client.flushdb()
    yield client
    await client.flushdb()
    await client.aclose()


@pytest.fixture
async def clean_tables(db_engine):
    """Truncate all tables before each test for isolation."""
    tables = [
        "risk_rejections",
        "screener_logs",
        "performance_snapshots",
        "research_cache",
        "reflection_logs",
        "playbook_versions",
        "trades",
    ]
    async with db_engine.begin() as conn:
        for table in tables:
            await conn.execute(text(f"TRUNCATE TABLE {table} CASCADE"))
