"""B2: Redis Stream data flow integration tests.

Verify publish/subscribe, consumer groups, ack, read_latest, and serialization
roundtrip using real Redis.
"""

from __future__ import annotations

import asyncio

import pytest

from orchestrator.models.messages import (
    MarketSnapshotMessage,
    StreamMessage,
    SystemAlertMessage,
    TradeFillMessage,
    TradeOrderMessage,
)
from orchestrator.redis_client import RedisClient

from .conftest import TEST_REDIS_URL

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _make_redis_client(group: str = "test_group", name: str = "test-1") -> RedisClient:
    """Create and connect a RedisClient to test Redis."""
    client = RedisClient(
        redis_url=TEST_REDIS_URL,
        consumer_group=group,
        consumer_name=name,
    )
    await client.connect()
    return client


# ---------------------------------------------------------------------------
# 1. Publish and subscribe MarketSnapshotMessage
# ---------------------------------------------------------------------------


async def test_publish_and_subscribe_market_snapshot(real_redis):
    """Publish MarketSnapshotMessage -> subscribe receives it."""
    client = await _make_redis_client()
    try:
        stream = "market:snapshots"
        msg = MarketSnapshotMessage(
            payload={"symbol": "BTC-USDT-SWAP", "regime": "trending_up"},
        )

        await client.publish(stream, msg)

        received: list[StreamMessage] = []

        async def _callback(s: str, m: StreamMessage) -> None:
            received.append(m)

        task = asyncio.create_task(client.subscribe([stream], _callback))
        await asyncio.sleep(0.5)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        assert len(received) == 1
        assert received[0].type == "market_snapshot"
        assert received[0].source == "indicator_server"
        assert received[0].payload["symbol"] == "BTC-USDT-SWAP"
    finally:
        await client.disconnect()


# ---------------------------------------------------------------------------
# 2. Publish and subscribe TradeOrderMessage
# ---------------------------------------------------------------------------


async def test_publish_and_subscribe_trade_order(real_redis):
    """Publish TradeOrderMessage -> consumer reads."""
    client = await _make_redis_client()
    try:
        stream = "trade:orders"
        msg = TradeOrderMessage(
            payload={"action": "OPEN_LONG", "symbol": "ETH-USDT-SWAP", "size": 0.1},
        )

        await client.publish(stream, msg)

        received: list[StreamMessage] = []

        async def _callback(s: str, m: StreamMessage) -> None:
            received.append(m)

        task = asyncio.create_task(client.subscribe([stream], _callback))
        await asyncio.sleep(0.5)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        assert len(received) == 1
        assert received[0].type == "trade_order"
        assert received[0].payload["action"] == "OPEN_LONG"
    finally:
        await client.disconnect()


# ---------------------------------------------------------------------------
# 3. Publish and subscribe TradeFillMessage
# ---------------------------------------------------------------------------


async def test_publish_and_subscribe_trade_fill(real_redis):
    """Publish TradeFillMessage -> consumer reads."""
    client = await _make_redis_client()
    try:
        stream = "trade:fills"
        msg = TradeFillMessage(
            payload={"order_id": "12345", "fill_price": 50000.0, "fill_size": 0.1},
        )

        await client.publish(stream, msg)

        received: list[StreamMessage] = []

        async def _callback(s: str, m: StreamMessage) -> None:
            received.append(m)

        task = asyncio.create_task(client.subscribe([stream], _callback))
        await asyncio.sleep(0.5)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        assert len(received) == 1
        assert received[0].type == "trade_fill"
        assert received[0].payload["order_id"] == "12345"
    finally:
        await client.disconnect()


# ---------------------------------------------------------------------------
# 4. Publish and subscribe SystemAlertMessage
# ---------------------------------------------------------------------------


async def test_publish_and_subscribe_system_alert(real_redis):
    """Publish SystemAlertMessage -> consumer reads."""
    client = await _make_redis_client()
    try:
        stream = "system:alerts"
        msg = SystemAlertMessage(
            source="orchestrator",
            payload={"severity": "CRITICAL", "message": "Daily loss limit hit"},
        )

        await client.publish(stream, msg)

        received: list[StreamMessage] = []

        async def _callback(s: str, m: StreamMessage) -> None:
            received.append(m)

        task = asyncio.create_task(client.subscribe([stream], _callback))
        await asyncio.sleep(0.5)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        assert len(received) == 1
        assert received[0].type == "system_alert"
        assert received[0].payload["severity"] == "CRITICAL"
    finally:
        await client.disconnect()


# ---------------------------------------------------------------------------
# 5. Multiple consumer groups receive same message
# ---------------------------------------------------------------------------


async def test_multiple_consumer_groups(real_redis):
    """3 consumers (orchestrator, indicator_trade, ui) all receive same message."""
    stream = "test:multi_consumer"

    clients = []
    for group in ["orchestrator", "indicator_trade", "ui"]:
        c = await _make_redis_client(group=group, name=f"{group}-1")
        await c.create_consumer_group(stream)
        clients.append(c)

    try:
        msg = SystemAlertMessage(
            source="test",
            payload={"event": "test_broadcast"},
        )
        await clients[0].publish(stream, msg)

        results: dict[str, list[StreamMessage]] = {
            "orchestrator": [],
            "indicator_trade": [],
            "ui": [],
        }

        async def _make_callback(group_name: str):
            async def _cb(s: str, m: StreamMessage) -> None:
                results[group_name].append(m)

            return _cb

        tasks = []
        for i, group in enumerate(["orchestrator", "indicator_trade", "ui"]):
            cb = await _make_callback(group)
            tasks.append(asyncio.create_task(clients[i].subscribe([stream], cb)))

        await asyncio.sleep(0.5)
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

        for group in ["orchestrator", "indicator_trade", "ui"]:
            assert len(results[group]) == 1, f"{group} did not receive message"
            assert results[group][0].payload["event"] == "test_broadcast"
    finally:
        for c in clients:
            await c.disconnect()


# ---------------------------------------------------------------------------
# 6. Message ack — not re-delivered
# ---------------------------------------------------------------------------


async def test_message_ack(real_redis):
    """After ack, message is not re-delivered on next read."""
    client = await _make_redis_client(group="ack_test")
    try:
        stream = "test:ack"
        await client.create_consumer_group(stream)
        msg = MarketSnapshotMessage(payload={"test": "ack"})
        await client.publish(stream, msg)

        # First read — should get the message
        received_1: list[StreamMessage] = []

        async def _cb1(s: str, m: StreamMessage) -> None:
            received_1.append(m)

        task = asyncio.create_task(client.subscribe([stream], _cb1))
        await asyncio.sleep(0.5)
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

        assert len(received_1) == 1

        # Second read — should NOT get the message (already acked)
        received_2: list[StreamMessage] = []

        async def _cb2(s: str, m: StreamMessage) -> None:
            received_2.append(m)

        task = asyncio.create_task(client.subscribe([stream], _cb2))
        await asyncio.sleep(0.5)
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

        assert len(received_2) == 0, "Message was re-delivered after ack"
    finally:
        await client.disconnect()


# ---------------------------------------------------------------------------
# 7. read_latest returns most recent message
# ---------------------------------------------------------------------------


async def test_read_latest(real_redis):
    """XREVRANGE returns most recent message."""
    client = await _make_redis_client()
    try:
        stream = "test:read_latest"
        msg1 = MarketSnapshotMessage(payload={"seq": 1})
        msg2 = MarketSnapshotMessage(payload={"seq": 2})
        msg3 = MarketSnapshotMessage(payload={"seq": 3})

        await client.publish(stream, msg1)
        await client.publish(stream, msg2)
        await client.publish(stream, msg3)

        latest = await client.read_latest(stream)
        assert latest is not None
        assert latest.payload["seq"] == 3
    finally:
        await client.disconnect()


# ---------------------------------------------------------------------------
# 8. Serialization roundtrip
# ---------------------------------------------------------------------------


async def test_stream_message_serialization_roundtrip(real_redis):
    """to_redis -> from_redis preserves all fields."""
    client = await _make_redis_client()
    try:
        stream = "test:roundtrip"
        original = MarketSnapshotMessage(
            source="indicator_server",
            payload={
                "symbol": "BTC-USDT-SWAP",
                "regime": "volatile",
                "indicators": {"rsi": 72.5, "atr": 450.0},
            },
            metadata={"timeframe": "1H", "candle_count": 200},
        )

        await client.publish(stream, original)
        restored = await client.read_latest(stream)

        assert restored is not None
        assert restored.type == original.type
        assert restored.source == original.source
        assert restored.payload == original.payload
        assert restored.metadata == original.metadata
        assert restored.msg_id == original.msg_id
    finally:
        await client.disconnect()
