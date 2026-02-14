"""B5: Position lifecycle integration tests.

Test open -> update -> close trade flow through real DB + Redis.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import text

from orchestrator.db.repository import TradeRepository
from orchestrator.models.messages import PositionUpdateMessage, TradeFillMessage
from orchestrator.redis_client import RedisClient

from .conftest import TEST_REDIS_URL

pytestmark = pytest.mark.integration

_NOW = datetime.now(timezone.utc)


def _trade_data(**overrides) -> dict:
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
# 1. Full lifecycle: open -> close with PnL
# ---------------------------------------------------------------------------


async def test_full_trade_lifecycle(session_factory, real_redis, clean_tables):
    """Open trade -> close with PnL -> verify DB state."""
    repo = TradeRepository(session_factory)

    # Open
    data = _trade_data()
    trade_id = await repo.create(data)
    open_trades = await repo.get_open()
    assert len(open_trades) == 1
    assert open_trades[0].status == "open"

    # Close with profit
    await repo.update(trade_id, {
        "status": "closed",
        "closed_at": _NOW + timedelta(hours=2),
        "duration_seconds": 7200,
        "exit_price": Decimal("51500.00"),
        "pnl_usd": 150.0,
        "pnl_pct": 0.03,
        "fees_usd": 2.5,
        "exit_reason": "take_profit",
    })

    # Verify
    open_trades = await repo.get_open()
    assert len(open_trades) == 0

    closed = await repo.get_recent_closed(limit=1)
    assert len(closed) == 1
    assert closed[0].trade_id == trade_id
    assert closed[0].pnl_usd == 150.0
    assert closed[0].exit_reason == "take_profit"
    assert closed[0].duration_seconds == 7200


# ---------------------------------------------------------------------------
# 2. Position update published to Redis -> read back
# ---------------------------------------------------------------------------


async def test_position_update_via_redis(real_redis):
    """Publish PositionUpdateMessage -> read_latest returns it."""
    client = RedisClient(
        redis_url=TEST_REDIS_URL,
        consumer_group="test_pos",
        consumer_name="test-1",
    )
    await client.connect()
    try:
        msg = PositionUpdateMessage(
            payload={
                "symbol": "BTC-USDT-SWAP",
                "direction": "LONG",
                "size": 0.1,
                "entry_price": 50000.0,
                "unrealized_pnl": 75.0,
                "status": "open",
            },
        )
        await client.publish("trade:positions", msg)

        latest = await client.read_latest("trade:positions")
        assert latest is not None
        assert latest.payload["symbol"] == "BTC-USDT-SWAP"
        assert latest.payload["status"] == "open"
        assert latest.payload["unrealized_pnl"] == 75.0
    finally:
        await client.disconnect()


# ---------------------------------------------------------------------------
# 3. Trade fill published to Redis -> read back
# ---------------------------------------------------------------------------


async def test_trade_fill_via_redis(real_redis):
    """Publish TradeFillMessage -> read_latest returns it."""
    client = RedisClient(
        redis_url=TEST_REDIS_URL,
        consumer_group="test_fill",
        consumer_name="test-1",
    )
    await client.connect()
    try:
        msg = TradeFillMessage(
            payload={
                "order_id": "okx-order-123",
                "symbol": "BTC-USDT-SWAP",
                "fill_price": 50050.0,
                "fill_size": 0.1,
                "side": "buy",
                "fee": 2.5,
            },
        )
        await client.publish("trade:fills", msg)

        latest = await client.read_latest("trade:fills")
        assert latest is not None
        assert latest.payload["order_id"] == "okx-order-123"
        assert latest.payload["fill_price"] == 50050.0
    finally:
        await client.disconnect()


# ---------------------------------------------------------------------------
# 4. Multiple positions tracked correctly
# ---------------------------------------------------------------------------


async def test_multiple_positions(session_factory, clean_tables):
    """Open 3 trades, close 1 -> get_open returns 2."""
    repo = TradeRepository(session_factory)

    ids = []
    for i, sym in enumerate(["BTC-USDT-SWAP", "ETH-USDT-SWAP", "SOL-USDT-SWAP"]):
        tid = await repo.create(_trade_data(
            symbol=sym,
            opened_at=_NOW - timedelta(hours=3 - i),
        ))
        ids.append(tid)

    # Close ETH
    await repo.update(ids[1], {
        "status": "closed",
        "closed_at": _NOW,
        "pnl_usd": -50.0,
        "exit_reason": "stop_loss",
    })

    open_trades = await repo.get_open()
    assert len(open_trades) == 2
    open_symbols = {t.symbol for t in open_trades}
    assert "BTC-USDT-SWAP" in open_symbols
    assert "SOL-USDT-SWAP" in open_symbols
    assert "ETH-USDT-SWAP" not in open_symbols

    closed = await repo.get_recent_closed()
    assert len(closed) == 1
    assert closed[0].symbol == "ETH-USDT-SWAP"
    assert closed[0].pnl_usd == -50.0
