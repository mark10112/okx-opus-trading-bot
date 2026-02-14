"""B11: Cross-service E2E integration tests.

Test full message flow across services using Redis Streams as the bus.
Simulates indicator-trade-server publishing snapshots, orchestrator consuming
and publishing orders, and trade-server publishing fills.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import text

from orchestrator.models.messages import (
    MarketSnapshotMessage,
    OpusDecisionMessage,
    SystemAlertMessage,
    TradeFillMessage,
    TradeOrderMessage,
)
from orchestrator.redis_client import RedisClient

from .conftest import TEST_REDIS_URL

pytestmark = pytest.mark.integration


async def _make_client(group: str, name: str = "t-1") -> RedisClient:
    client = RedisClient(redis_url=TEST_REDIS_URL, consumer_group=group, consumer_name=name)
    await client.connect()
    return client


# ---------------------------------------------------------------------------
# 1. Full message chain: snapshot -> order -> fill
# ---------------------------------------------------------------------------


async def test_full_message_chain(real_redis):
    """Simulate full cross-service flow: snapshot -> order -> fill."""
    # Three clients simulating three services
    indicator = await _make_client("indicator_trade")
    orchestrator = await _make_client("orchestrator")
    trade_srv = await _make_client("trade_server")

    try:
        # 1. Indicator server publishes market snapshot
        snapshot = MarketSnapshotMessage(
            payload={
                "symbol": "BTC-USDT-SWAP",
                "timeframe": "5m",
                "close": 50000.0,
                "rsi": 55.0,
                "regime": "trending_up",
            },
        )
        await indicator.publish("market:snapshots", snapshot)

        # 2. Orchestrator reads snapshot
        snap_msg = await orchestrator.read_latest("market:snapshots")
        assert snap_msg is not None
        assert snap_msg.payload["symbol"] == "BTC-USDT-SWAP"

        # 3. Orchestrator publishes trade order
        order = TradeOrderMessage(
            payload={
                "action": "OPEN_LONG",
                "symbol": "BTC-USDT-SWAP",
                "size_pct": 0.02,
                "entry_price": 50000.0,
                "stop_loss": 49500.0,
                "take_profit": 51500.0,
            },
        )
        await orchestrator.publish("trade:orders", order)

        # 4. Trade server reads order
        order_msg = await trade_srv.read_latest("trade:orders")
        assert order_msg is not None
        assert order_msg.payload["action"] == "OPEN_LONG"

        # 5. Trade server publishes fill
        fill = TradeFillMessage(
            payload={
                "order_id": "okx-123",
                "symbol": "BTC-USDT-SWAP",
                "fill_price": 50010.0,
                "fill_size": 0.1,
                "side": "buy",
                "fee": 2.5,
            },
        )
        await trade_srv.publish("trade:fills", fill)

        # 6. Orchestrator reads fill
        fill_msg = await orchestrator.read_latest("trade:fills")
        assert fill_msg is not None
        assert fill_msg.payload["fill_price"] == 50010.0

    finally:
        await indicator.disconnect()
        await orchestrator.disconnect()
        await trade_srv.disconnect()


# ---------------------------------------------------------------------------
# 2. Orchestrator decision -> UI alert stream
# ---------------------------------------------------------------------------


async def test_orchestrator_to_ui_alert_flow(real_redis):
    """Orchestrator publishes decision + alert -> UI service reads both."""
    orchestrator = await _make_client("orchestrator_e2e")
    ui_service = await _make_client("ui_e2e")

    try:
        # Orchestrator publishes opus decision
        decision = OpusDecisionMessage(
            payload={
                "action": "OPEN_LONG",
                "symbol": "BTC-USDT-SWAP",
                "confidence": 0.85,
                "reasoning": "Strong momentum signal",
            },
        )
        await orchestrator.publish("opus:decisions", decision)

        # Orchestrator publishes system alert
        alert = SystemAlertMessage(
            source="orchestrator",
            payload={"severity": "INFO", "reason": "New trade opened"},
        )
        await orchestrator.publish("system:alerts", alert)

        # UI reads decision
        dec_msg = await ui_service.read_latest("opus:decisions")
        assert dec_msg is not None
        assert dec_msg.payload["confidence"] == 0.85

        # UI reads alert
        alert_msg = await ui_service.read_latest("system:alerts")
        assert alert_msg is not None
        assert alert_msg.payload["severity"] == "INFO"

    finally:
        await orchestrator.disconnect()
        await ui_service.disconnect()


# ---------------------------------------------------------------------------
# 3. Consumer group isolation: two consumers on same stream
# ---------------------------------------------------------------------------


async def test_consumer_group_isolation(real_redis):
    """Two different consumer groups both receive the same message."""
    publisher = await _make_client("publisher_e2e")
    consumer_a = await _make_client("group_a")
    consumer_b = await _make_client("group_b")

    try:
        stream = "test:e2e:isolation"

        # Create consumer groups
        await consumer_a.create_consumer_group(stream)
        await consumer_b.create_consumer_group(stream)

        # Publish one message
        msg = MarketSnapshotMessage(payload={"test": "isolation"})
        await publisher.publish(stream, msg)

        # Both consumers should be able to read the latest
        msg_a = await consumer_a.read_latest(stream)
        msg_b = await consumer_b.read_latest(stream)

        assert msg_a is not None
        assert msg_b is not None
        assert msg_a.payload["test"] == "isolation"
        assert msg_b.payload["test"] == "isolation"

    finally:
        await publisher.disconnect()
        await consumer_a.disconnect()
        await consumer_b.disconnect()


# ---------------------------------------------------------------------------
# 4. End-to-end: Redis message -> DB persistence roundtrip
# ---------------------------------------------------------------------------


async def test_redis_to_db_roundtrip(real_redis, session_factory):
    """Publish trade order via Redis -> journal to DB -> read back."""
    from orchestrator.db.repository import TradeRepository

    client = await _make_client("e2e_db")
    repo = TradeRepository(session_factory)

    try:
        # Publish order
        order = TradeOrderMessage(
            payload={
                "action": "OPEN_LONG",
                "symbol": "BTC-USDT-SWAP",
                "entry_price": 50000.0,
                "stop_loss": 49500.0,
                "take_profit": 51500.0,
                "size_pct": 0.02,
            },
        )
        await client.publish("trade:orders", order)

        # Read from Redis
        order_msg = await client.read_latest("trade:orders")
        assert order_msg is not None

        # Journal to DB (simulating orchestrator's journaling step)
        # direction column is varchar(5), so map action to short form
        action = order_msg.payload["action"]
        direction = "LONG" if "LONG" in action else "SHORT"

        trade_id = await repo.create({
            "trade_id": str(uuid.uuid4()),
            "opened_at": datetime.now(timezone.utc),
            "symbol": order_msg.payload["symbol"],
            "direction": direction,
            "entry_price": order_msg.payload["entry_price"],
            "stop_loss": order_msg.payload["stop_loss"],
            "take_profit": order_msg.payload["take_profit"],
            "size": 0.1,
            "status": "open",
            "strategy_used": "momentum",
            "confidence_at_entry": 0.85,
            "market_regime": "trending_up",
        })

        # Read back from DB
        open_trades = await repo.get_open()
        matching = [t for t in open_trades if t.trade_id == trade_id]
        assert len(matching) == 1
        assert matching[0].symbol == "BTC-USDT-SWAP"
        assert matching[0].direction == "LONG"

    finally:
        await client.disconnect()
