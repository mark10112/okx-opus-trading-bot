"""B3: Database repository integration tests.

Verify all 7 repositories against real PostgreSQL with real migrations.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import text

from orchestrator.db.repository import (
    PerformanceSnapshotRepository,
    PlaybookRepository,
    ReflectionRepository,
    ResearchCacheRepository,
    RiskRejectionRepository,
    ScreenerLogRepository,
    TradeRepository,
)

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOW = datetime.now(timezone.utc)


def _trade_data(**overrides) -> dict:
    """Minimal valid trade dict."""
    base = {
        "trade_id": str(uuid.uuid4()),
        "opened_at": _NOW,
        "symbol": "BTC-USDT-SWAP",
        "direction": "LONG",
        "entry_price": Decimal("50000.00"),
        "stop_loss": Decimal("49000.00"),
        "take_profit": Decimal("52000.00"),
        "size": Decimal("0.1"),
        "leverage": Decimal("2.0"),
        "strategy_used": "momentum",
        "confidence_at_entry": Decimal("0.85"),
        "market_regime": "trending_up",
        "status": "open",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# 1. Trade create and get
# ---------------------------------------------------------------------------


async def test_trade_create_and_get(session_factory, clean_tables):
    """Insert trade -> get_open returns it."""
    repo = TradeRepository(session_factory)
    trade_id = await repo.create(_trade_data())

    assert trade_id  # non-empty string

    open_trades = await repo.get_open()
    assert len(open_trades) == 1
    assert open_trades[0].trade_id == trade_id
    assert open_trades[0].symbol == "BTC-USDT-SWAP"
    assert open_trades[0].direction == "LONG"
    assert open_trades[0].status == "open"


# ---------------------------------------------------------------------------
# 2. Trade update close
# ---------------------------------------------------------------------------


async def test_trade_update_close(session_factory, clean_tables):
    """Update status=closed -> get_open excludes it."""
    repo = TradeRepository(session_factory)
    trade_id = await repo.create(_trade_data())

    await repo.update(trade_id, {
        "status": "closed",
        "closed_at": _NOW + timedelta(hours=1),
        "exit_price": Decimal("51000.00"),
        "pnl_usd": 100.0,
        "pnl_pct": 0.02,
        "exit_reason": "take_profit",
    })

    open_trades = await repo.get_open()
    assert len(open_trades) == 0

    closed = await repo.get_recent_closed(limit=10)
    assert len(closed) == 1
    assert closed[0].trade_id == trade_id
    assert closed[0].status == "closed"
    assert closed[0].pnl_usd == 100.0


# ---------------------------------------------------------------------------
# 3. Trade get_recent_closed ordered by close_time
# ---------------------------------------------------------------------------


async def test_trade_get_recent_closed(session_factory, clean_tables):
    """Multiple trades -> returns ordered by closed_at desc."""
    repo = TradeRepository(session_factory)

    for i in range(3):
        tid = await repo.create(_trade_data(
            opened_at=_NOW - timedelta(hours=3 - i),
        ))
        await repo.update(tid, {
            "status": "closed",
            "closed_at": _NOW - timedelta(hours=2 - i),
            "pnl_usd": float(i * 50),
        })

    closed = await repo.get_recent_closed(limit=10)
    assert len(closed) == 3
    # Most recent first
    assert closed[0].pnl_usd > closed[2].pnl_usd


# ---------------------------------------------------------------------------
# 4. Playbook save and get_latest
# ---------------------------------------------------------------------------


async def test_playbook_save_and_get_latest(session_factory, clean_tables):
    """Save v1, v2 -> get_latest returns v2."""
    repo = PlaybookRepository(session_factory)

    await repo.save_version({
        "version": 1,
        "playbook_json": {"rules": ["rule1"]},
        "change_summary": "Initial",
        "triggered_by": "init",
    })
    await repo.save_version({
        "version": 2,
        "playbook_json": {"rules": ["rule1", "rule2"]},
        "change_summary": "Added rule2",
        "triggered_by": "reflection",
    })

    latest = await repo.get_latest()
    assert latest is not None
    assert latest["version"] == 2
    assert "rule2" in latest["playbook_json"]["rules"]


# ---------------------------------------------------------------------------
# 5. Playbook history
# ---------------------------------------------------------------------------


async def test_playbook_history(session_factory, clean_tables):
    """Save 3 versions -> get_history returns all ordered."""
    repo = PlaybookRepository(session_factory)

    for v in range(1, 4):
        await repo.save_version({
            "version": v,
            "playbook_json": {"v": v},
            "change_summary": f"Version {v}",
            "triggered_by": "reflection" if v > 1 else "init",
        })

    history = await repo.get_history()
    assert len(history) == 3
    assert history[0]["version"] == 3  # desc order
    assert history[2]["version"] == 1


# ---------------------------------------------------------------------------
# 6. Reflection save and get_last_time
# ---------------------------------------------------------------------------


async def test_reflection_save_and_get(session_factory, clean_tables):
    """Save reflection -> get_last_time correct."""
    repo = ReflectionRepository(session_factory)

    # No reflections yet
    last = await repo.get_last_time()
    assert last is None

    await repo.save({
        "reflection_type": "post_trade",
        "trade_ids": [1, 2],
        "output_json": {"lessons": ["lesson1"]},
    })

    last = await repo.get_last_time()
    assert last is not None
    assert isinstance(last, datetime)


# ---------------------------------------------------------------------------
# 7. Screener log and update
# ---------------------------------------------------------------------------


async def test_screener_log_and_update(session_factory, clean_tables):
    """Log screener -> update_opus_agreement."""
    repo = ScreenerLogRepository(session_factory)

    log_id = await repo.log({
        "symbol": "BTC-USDT-SWAP",
        "signal": True,
        "reason": "Strong momentum",
        "latency_ms": 150,
    })

    assert log_id > 0

    await repo.update_opus_agreement(log_id, opus_action="OPEN_LONG", agreed=True)

    # Verify via direct query
    async with session_factory() as session:
        result = await session.execute(
            text("SELECT opus_action, opus_agreed FROM screener_logs WHERE id = :id"),
            {"id": log_id},
        )
        row = result.fetchone()
    assert row is not None
    assert row[0] == "OPEN_LONG"
    assert row[1] is True


# ---------------------------------------------------------------------------
# 8. Research cache TTL
# ---------------------------------------------------------------------------


async def test_research_cache_ttl(session_factory, clean_tables):
    """Save -> get_cached within TTL -> get_cached after TTL returns None."""
    from orchestrator.db.models import ResearchCacheORM

    repo = ResearchCacheRepository(session_factory)

    # Insert with explicit server-side NOW() to avoid naive datetime timezone issues
    async with session_factory() as session:
        await session.execute(
            text(
                "INSERT INTO research_cache (query, response_json, created_at) "
                "VALUES (:q, :r, NOW())"
            ),
            {"q": "BTC outlook", "r": '{"summary": "Bullish"}'},
        )
        await session.commit()

    # Within TTL (3600s default)
    cached = await repo.get_cached("BTC outlook", ttl_seconds=3600)
    assert cached is not None, "get_cached returned None for fresh entry"
    assert cached["summary"] == "Bullish"

    # Insert an old entry (2 hours ago) to test expiry
    async with session_factory() as session:
        await session.execute(
            text(
                "INSERT INTO research_cache (query, response_json, created_at) "
                "VALUES (:q, :r, NOW() - INTERVAL '2 hours')"
            ),
            {"q": "ETH outlook", "r": '{"summary": "Bearish"}'},
        )
        await session.commit()

    # Should be expired with 1-hour TTL
    expired = await repo.get_cached("ETH outlook", ttl_seconds=3600)
    assert expired is None

    # Non-existent query
    missing = await repo.get_cached("SOL outlook")
    assert missing is None


# ---------------------------------------------------------------------------
# 9. Risk rejection log
# ---------------------------------------------------------------------------


async def test_risk_rejection_log(session_factory, clean_tables):
    """Log rejection -> verify in DB."""
    repo = RiskRejectionRepository(session_factory)

    log_id = await repo.log(
        decision={"action": "OPEN_LONG", "size": 10.0},
        failed_rules=["max_position_count", "trade_size_pct"],
        account_state={"equity": 10000.0, "open_positions": 3},
    )

    assert log_id > 0

    # Verify via direct query
    async with session_factory() as session:
        result = await session.execute(
            text("SELECT decision_json, failed_rules FROM risk_rejections WHERE id = :id"),
            {"id": log_id},
        )
        row = result.fetchone()
    assert row is not None
    assert row[0]["action"] == "OPEN_LONG"
    assert "max_position_count" in row[1]


# ---------------------------------------------------------------------------
# 10. Performance snapshot save
# ---------------------------------------------------------------------------


async def test_performance_snapshot_save(session_factory, clean_tables):
    """Save snapshot -> verify fields."""
    repo = PerformanceSnapshotRepository(session_factory)

    snap_id = await repo.save("daily", {
        "equity": Decimal("10500.00"),
        "total_pnl": Decimal("500.00"),
        "win_rate": Decimal("0.65"),
        "profit_factor": Decimal("2.10"),
        "sharpe_ratio": Decimal("1.80"),
        "max_drawdown": Decimal("-0.03"),
        "total_trades": 20,
        "metrics_json": {"avg_hold_time": 3600},
    })

    assert snap_id > 0

    # Verify via direct query
    async with session_factory() as session:
        result = await session.execute(
            text("SELECT equity, win_rate, total_trades FROM performance_snapshots WHERE id = :id"),
            {"id": snap_id},
        )
        row = result.fetchone()
    assert row is not None
    assert float(row[0]) == 10500.0
    assert float(row[1]) == 0.65
    assert row[2] == 20


# ---------------------------------------------------------------------------
# 11. Candle upsert and get (via direct SQL — no CandleRepository in orchestrator)
# ---------------------------------------------------------------------------


async def test_candle_upsert_and_get(db_engine):
    """Upsert candle -> get_recent returns it."""
    async with db_engine.begin() as conn:
        # Clean candles
        await conn.execute(text("DELETE FROM candles"))

        # Insert
        await conn.execute(
            text(
                "INSERT INTO candles (time, symbol, timeframe, open, high, low, close, volume) "
                "VALUES (:t, :s, :tf, :o, :h, :l, :c, :v) "
                "ON CONFLICT (time, symbol, timeframe) DO UPDATE SET close = EXCLUDED.close"
            ),
            {
                "t": _NOW,
                "s": "BTC-USDT-SWAP",
                "tf": "1H",
                "o": 50000.0,
                "h": 50500.0,
                "l": 49800.0,
                "c": 50200.0,
                "v": 1234.5,
            },
        )

        # Read back
        result = await conn.execute(
            text(
                "SELECT symbol, timeframe, close FROM candles "
                "WHERE symbol = 'BTC-USDT-SWAP' AND timeframe = '1H' "
                "ORDER BY time DESC LIMIT 1"
            )
        )
        row = result.fetchone()

    assert row is not None
    assert row[0] == "BTC-USDT-SWAP"
    assert row[1] == "1H"
    assert float(row[2]) == 50200.0
