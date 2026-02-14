"""Shared fixtures for ui integration tests.

Requires docker-compose.test.yml running (Postgres on 5433, Redis on 6380).
Requires orchestrator alembic migrations to have been applied already
(run orchestrator integration tests first, or `alembic upgrade head`).
"""

from __future__ import annotations

import os
import subprocess
import sys

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:testpass@localhost:5433/trading_bot_test",
)
TEST_REDIS_URL = os.environ.get("TEST_REDIS_URL", "redis://localhost:6380")

_engine = None

# Path to orchestrator for running alembic
_ORCHESTRATOR_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "orchestrator"
)


@pytest.fixture(scope="session", autouse=True)
def _ensure_migrations():
    """Run orchestrator alembic migrations via subprocess."""
    env = os.environ.copy()
    env["DATABASE_URL"] = TEST_DATABASE_URL
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "002"],
        cwd=_ORCHESTRATOR_DIR,
        env=env,
        capture_output=True,
    )


@pytest.fixture(scope="session")
def db_engine():
    """Session-scoped async engine for direct SQL queries."""
    global _engine
    if _engine is None:
        _engine = create_async_engine(TEST_DATABASE_URL, echo=False, poolclass=NullPool)
    return _engine


@pytest.fixture(scope="session")
def session_factory(db_engine):
    """Session-scoped async session factory."""
    return async_sessionmaker(db_engine, expire_on_commit=False)
