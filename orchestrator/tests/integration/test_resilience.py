"""B7: Resilience integration tests.

Test error handling, reconnection, and graceful degradation.
"""

from __future__ import annotations

import asyncio

import pytest
import redis.asyncio as aioredis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from orchestrator.models.messages import MarketSnapshotMessage, StreamMessage
from orchestrator.redis_client import RedisClient

from .conftest import TEST_DATABASE_URL, TEST_REDIS_URL

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# 1. Redis publish after reconnect
# ---------------------------------------------------------------------------


async def test_redis_publish_after_reconnect(real_redis):
    """Disconnect and reconnect Redis client -> publish still works."""
    client = RedisClient(
        redis_url=TEST_REDIS_URL,
        consumer_group="test_reconnect",
        consumer_name="test-1",
    )
    await client.connect()

    try:
        # First publish
        msg1 = MarketSnapshotMessage(payload={"seq": 1})
        await client.publish("test:reconnect", msg1)

        # Disconnect
        await client.disconnect()

        # Reconnect
        await client.connect()

        # Second publish after reconnect
        msg2 = MarketSnapshotMessage(payload={"seq": 2})
        await client.publish("test:reconnect", msg2)

        latest = await client.read_latest("test:reconnect")
        assert latest is not None
        assert latest.payload["seq"] == 2
    finally:
        await client.disconnect()


# ---------------------------------------------------------------------------
# 2. DB query after connection drop (NullPool creates fresh connections)
# ---------------------------------------------------------------------------


async def test_db_query_after_fresh_connection(db_engine):
    """Multiple sequential queries work with NullPool (fresh connections)."""
    # First query
    async with db_engine.connect() as conn:
        result = await conn.execute(text("SELECT 1"))
        assert result.scalar() == 1

    # Second query (new connection from NullPool)
    async with db_engine.connect() as conn:
        result = await conn.execute(text("SELECT 2"))
        assert result.scalar() == 2

    # Third query with table access
    async with db_engine.connect() as conn:
        result = await conn.execute(
            text("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public'")
        )
        count = result.scalar()
        assert count > 0


# ---------------------------------------------------------------------------
# 3. Redis FLUSHDB doesn't break consumer groups
# ---------------------------------------------------------------------------


async def test_redis_flushdb_recovery(real_redis):
    """After FLUSHDB, consumer groups can be recreated."""
    client = RedisClient(
        redis_url=TEST_REDIS_URL,
        consumer_group="test_flush_recovery",
        consumer_name="test-1",
    )
    await client.connect()

    try:
        # Publish and verify
        msg = MarketSnapshotMessage(payload={"before": "flush"})
        await client.publish("test:flush_recovery", msg)

        # FLUSHDB destroys everything
        await client.client.flushdb()

        # Recreate consumer group and publish again
        await client.create_consumer_group("test:flush_recovery")
        msg2 = MarketSnapshotMessage(payload={"after": "flush"})
        await client.publish("test:flush_recovery", msg2)

        latest = await client.read_latest("test:flush_recovery")
        assert latest is not None
        assert latest.payload.get("after") == "flush"
    finally:
        await client.disconnect()


# ---------------------------------------------------------------------------
# 4. Concurrent DB writes don't conflict
# ---------------------------------------------------------------------------


async def test_concurrent_db_writes(db_engine):
    """Multiple concurrent INSERT operations succeed without deadlock."""
    import uuid

    async def _insert_trade(i: int) -> None:
        async with db_engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO trades (trade_id, opened_at, symbol, direction, "
                    "entry_price, stop_loss, size, status) "
                    "VALUES (:tid, NOW(), :sym, 'LONG', 50000, 49000, 0.1, 'open')"
                ),
                {"tid": str(uuid.uuid4()), "sym": f"TEST-{i}-SWAP"},
            )

    # Run 5 concurrent inserts
    await asyncio.gather(*[_insert_trade(i) for i in range(5)])

    # Verify all 5 inserted
    async with db_engine.connect() as conn:
        result = await conn.execute(
            text("SELECT COUNT(*) FROM trades WHERE symbol LIKE 'TEST-%-SWAP'")
        )
        count = result.scalar()
    assert count == 5

    # Cleanup
    async with db_engine.begin() as conn:
        await conn.execute(text("DELETE FROM trades WHERE symbol LIKE 'TEST-%-SWAP'"))


# ---------------------------------------------------------------------------
# 5. Redis stream message with invalid data doesn't crash subscribe loop
# ---------------------------------------------------------------------------


async def test_invalid_redis_message_handled(real_redis):
    """Invalid message data in stream doesn't crash the subscribe loop."""
    client = RedisClient(
        redis_url=TEST_REDIS_URL,
        consumer_group="test_invalid",
        consumer_name="test-1",
    )
    await client.connect()

    try:
        stream = "test:invalid_msg"
        await client.create_consumer_group(stream)

        # Publish invalid data directly (not via StreamMessage)
        await client.client.xadd(stream, {b"data": b"not-valid-json"})

        # Also publish a valid message
        valid = MarketSnapshotMessage(payload={"valid": True})
        await client.publish(stream, valid)

        received: list[StreamMessage] = []

        async def _cb(s: str, m: StreamMessage) -> None:
            received.append(m)

        task = asyncio.create_task(client.subscribe([stream], _cb))
        await asyncio.sleep(1.0)
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

        # The valid message should have been received (invalid one logged as error)
        assert len(received) >= 1
        assert any(m.payload.get("valid") is True for m in received)
    finally:
        await client.disconnect()


# ---------------------------------------------------------------------------
# 6. Graceful shutdown: Redis client disconnect is idempotent
# ---------------------------------------------------------------------------


async def test_redis_disconnect_idempotent(real_redis):
    """Calling disconnect multiple times doesn't raise."""
    client = RedisClient(
        redis_url=TEST_REDIS_URL,
        consumer_group="test_idempotent",
        consumer_name="test-1",
    )
    await client.connect()

    # Disconnect twice — should not raise
    await client.disconnect()
    await client.disconnect()
