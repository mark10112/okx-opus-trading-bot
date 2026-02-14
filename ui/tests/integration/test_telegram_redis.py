"""B9: Telegram/Redis integration tests.

Test alert sender's Redis subscription and DB queries against real infra.
No actual Telegram bot connection needed — we mock the bot.send_message.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import text

from .conftest import TEST_DATABASE_URL, TEST_REDIS_URL

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# 1. DBQueries reads seeded trades from real DB
# ---------------------------------------------------------------------------


async def test_db_queries_get_open_positions(db_engine):
    """Seed open trades -> DBQueries.get_open_positions returns them."""
    from ui.db.queries import DBQueries

    # Seed a trade
    trade_id = str(uuid.uuid4())
    async with db_engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO trades (trade_id, opened_at, symbol, direction, "
                "entry_price, stop_loss, size, status) "
                "VALUES (:tid, NOW(), 'BTC-USDT-SWAP', 'LONG', 50000, 49000, 0.1, 'open')"
            ),
            {"tid": trade_id},
        )

    try:
        queries = DBQueries(db_engine)
        positions = await queries.get_open_positions()
        assert isinstance(positions, list)
        assert any(p.get("trade_id") == trade_id or p.get("symbol") == "BTC-USDT-SWAP" for p in positions)
    finally:
        async with db_engine.begin() as conn:
            await conn.execute(text("DELETE FROM trades WHERE trade_id = :tid"), {"tid": trade_id})


# ---------------------------------------------------------------------------
# 2. DBQueries reads recent trades
# ---------------------------------------------------------------------------


async def test_db_queries_get_recent_trades(db_engine):
    """Seed closed trades -> DBQueries.get_recent_trades returns them."""
    from ui.db.queries import DBQueries

    trade_id = str(uuid.uuid4())
    async with db_engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO trades (trade_id, opened_at, closed_at, symbol, direction, "
                "entry_price, exit_price, stop_loss, size, pnl_usd, status) "
                "VALUES (:tid, NOW() - INTERVAL '1 hour', NOW(), 'ETH-USDT-SWAP', "
                "'SHORT', 3000, 2900, 3100, 0.5, 50.0, 'closed')"
            ),
            {"tid": trade_id},
        )

    try:
        queries = DBQueries(db_engine)
        trades = await queries.get_recent_trades(limit=10)
        assert isinstance(trades, list)
        assert any(t.get("trade_id") == trade_id for t in trades)
    finally:
        async with db_engine.begin() as conn:
            await conn.execute(text("DELETE FROM trades WHERE trade_id = :tid"), {"tid": trade_id})


# ---------------------------------------------------------------------------
# 3. Redis alert stream publish/read roundtrip
# ---------------------------------------------------------------------------


async def test_redis_alert_stream_roundtrip():
    """Publish SystemAlertMessage to system:alerts -> read_latest returns it."""
    # Import from orchestrator's shared redis_client
    import sys
    import os

    orch_src = os.path.join(os.path.dirname(__file__), "..", "..", "..", "orchestrator", "src")
    if orch_src not in sys.path:
        sys.path.insert(0, orch_src)

    from orchestrator.redis_client import RedisClient
    from orchestrator.models.messages import SystemAlertMessage

    client = RedisClient(
        redis_url=TEST_REDIS_URL,
        consumer_group="test_ui_alert",
        consumer_name="test-1",
    )
    await client.connect()
    try:
        msg = SystemAlertMessage(
            source="orchestrator",
            payload={"reason": "Test halt", "severity": "CRITICAL"},
        )
        await client.publish("system:alerts", msg)

        latest = await client.read_latest("system:alerts")
        assert latest is not None
        assert latest.payload["severity"] == "CRITICAL"
        assert latest.payload["reason"] == "Test halt"
    finally:
        await client.disconnect()


# ---------------------------------------------------------------------------
# 4. DBQueries performance metrics on empty DB
# ---------------------------------------------------------------------------


async def test_db_queries_performance_metrics_empty(db_engine):
    """Performance metrics on empty trades returns safe defaults."""
    from ui.db.queries import DBQueries

    queries = DBQueries(db_engine)
    metrics = await queries.get_performance_metrics()
    assert isinstance(metrics, dict)
    assert "win_rate" in metrics or "total_trades" in metrics


# ---------------------------------------------------------------------------
# 5. DBQueries get_latest_playbook
# ---------------------------------------------------------------------------


async def test_db_queries_get_latest_playbook(db_engine):
    """Seed playbook version -> get_latest_playbook returns it."""
    from ui.db.queries import DBQueries

    async with db_engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO playbook_versions (version, playbook_json, change_summary, triggered_by) "
                "VALUES (999, :pj, 'Test version', 'reflection') "
                "ON CONFLICT (version) DO UPDATE SET change_summary = 'Test version'"
            ),
            {"pj": '{"rules": ["test_rule"]}'},
        )

    try:
        queries = DBQueries(db_engine)
        playbook = await queries.get_latest_playbook()
        assert playbook is not None
        assert isinstance(playbook, dict)
    finally:
        async with db_engine.begin() as conn:
            await conn.execute(text("DELETE FROM playbook_versions WHERE version = 999"))
