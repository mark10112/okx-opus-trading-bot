"""B1: Infrastructure integration tests.

Verify Postgres, Redis, Alembic migrations, TimescaleDB, and consumer groups.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# 1. PostgreSQL connection
# ---------------------------------------------------------------------------


async def test_postgres_connection(db_engine):
    """Connect to test Postgres and execute SELECT 1."""
    async with db_engine.connect() as conn:
        result = await conn.execute(text("SELECT 1 AS ok"))
        row = result.fetchone()
    assert row is not None
    assert row[0] == 1


# ---------------------------------------------------------------------------
# 2. Redis connection
# ---------------------------------------------------------------------------


async def test_redis_connection(real_redis):
    """Connect to test Redis and PING."""
    pong = await real_redis.ping()
    assert pong is True


# ---------------------------------------------------------------------------
# 3. Alembic upgrade head — tables exist
# ---------------------------------------------------------------------------

EXPECTED_TABLES = [
    "trades",
    "playbook_versions",
    "reflection_logs",
    "research_cache",
    "performance_snapshots",
    "risk_rejections",
    "candles",
    "screener_logs",
]


async def test_alembic_upgrade_head(db_engine):
    """After upgrade head, all expected tables should exist."""
    async with db_engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"
            )
        )
        tables = {row[0] for row in result.fetchall()}

    for expected in EXPECTED_TABLES:
        assert expected in tables, f"Table '{expected}' not found after migration"


# ---------------------------------------------------------------------------
# 4. Trades table has correct columns
# ---------------------------------------------------------------------------


async def test_alembic_tables_have_correct_columns(db_engine):
    """Spot-check that trades table has key columns."""
    async with db_engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'trades' ORDER BY ordinal_position"
            )
        )
        columns = {row[0] for row in result.fetchall()}

    for col in ["trade_id", "symbol", "direction", "entry_price", "stop_loss", "status"]:
        assert col in columns, f"Column '{col}' missing from trades table"


# ---------------------------------------------------------------------------
# 5. TimescaleDB hypertable
# ---------------------------------------------------------------------------


async def test_timescaledb_hypertable(db_engine):
    """Verify candles is a TimescaleDB hypertable."""
    async with db_engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT hypertable_name FROM timescaledb_information.hypertables "
                "WHERE hypertable_name = 'candles'"
            )
        )
        row = result.fetchone()

    assert row is not None, "candles is not a TimescaleDB hypertable"
    assert row[0] == "candles"


# ---------------------------------------------------------------------------
# 6. grafana_reader user
# ---------------------------------------------------------------------------


async def test_grafana_reader_user(db_engine):
    """Verify grafana_reader role exists after migration 003."""
    async with db_engine.connect() as conn:
        result = await conn.execute(
            text("SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'grafana_reader'")
        )
        row = result.fetchone()

    assert row is not None, "grafana_reader role does not exist"


# ---------------------------------------------------------------------------
# 7. Redis consumer groups
# ---------------------------------------------------------------------------


async def test_redis_consumer_groups(real_redis):
    """Create consumer groups for all 3 services and verify via XINFO."""
    groups = ["orchestrator", "indicator_trade", "ui"]
    stream = "test:consumer_groups"

    # Ensure stream exists
    await real_redis.xadd(stream, {b"data": b"init"})

    for group in groups:
        try:
            await real_redis.xgroup_create(stream, group, id="0", mkstream=True)
        except Exception:
            pass  # BUSYGROUP — already exists

    info = await real_redis.xinfo_groups(stream)
    group_names = {
        g["name"].decode() if isinstance(g["name"], bytes) else g["name"] for g in info
    }

    for group in groups:
        assert group in group_names, f"Consumer group '{group}' not found"
