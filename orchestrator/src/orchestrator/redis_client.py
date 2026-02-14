"""Redis Streams publish/subscribe client."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

import redis.asyncio as aioredis
import structlog

from orchestrator.models.messages import StreamMessage

logger = structlog.get_logger()

STREAMS = [
    "market:snapshots",
    "market:alerts",
    "trade:fills",
    "trade:positions",
    "trade:orders",
    "opus:decisions",
    "system:alerts",
]


class RedisClient:
    def __init__(
        self,
        redis_url: str = "redis://redis:6379",
        consumer_group: str = "orchestrator",
        consumer_name: str = "orch-1",
        socket_timeout: float = 30.0,
        socket_connect_timeout: float = 10.0,
        retry_on_timeout: bool = True,
    ) -> None:
        self.redis_url = redis_url
        self.consumer_group = consumer_group
        self.consumer_name = consumer_name
        self.socket_timeout = socket_timeout
        self.socket_connect_timeout = socket_connect_timeout
        self.retry_on_timeout = retry_on_timeout
        self.client: aioredis.Redis | None = None

    async def connect(self) -> None:
        """Connect to Redis, create consumer groups if not exist."""
        self.client = aioredis.from_url(
            self.redis_url,
            decode_responses=False,
            max_connections=20,
            socket_timeout=self.socket_timeout,
            socket_connect_timeout=self.socket_connect_timeout,
            retry_on_timeout=self.retry_on_timeout,
        )
        await self.client.ping()
        logger.info("redis_connected", url=self.redis_url, group=self.consumer_group)

        for stream in STREAMS:
            await self.create_consumer_group(stream)

    async def disconnect(self) -> None:
        """Close Redis connection."""
        if self.client:
            await self.client.aclose()
            logger.info("redis_disconnected")

    async def publish(self, stream: str, message: StreamMessage) -> str:
        """XADD message to stream. Returns message ID."""
        assert self.client is not None
        msg_id = await self.client.xadd(stream, message.to_redis())
        logger.debug("redis_published", stream=stream, msg_id=msg_id, type=message.type)
        return msg_id.decode() if isinstance(msg_id, bytes) else msg_id

    async def subscribe(
        self,
        streams: list[str],
        callback: Callable[[str, StreamMessage], Awaitable[None]],
    ) -> None:
        """XREADGROUP blocking loop. Calls callback(stream_name, message) for each new message."""
        assert self.client is not None
        stream_dict = {s: ">" for s in streams}

        while True:
            try:
                results = await self.client.xreadgroup(
                    groupname=self.consumer_group,
                    consumername=self.consumer_name,
                    streams=stream_dict,
                    count=10,
                    block=5000,
                )
                if not results:
                    continue

                for stream_bytes, messages in results:
                    stream_name = (
                        stream_bytes.decode() if isinstance(stream_bytes, bytes) else stream_bytes
                    )
                    for msg_id, data in messages:
                        try:
                            message = StreamMessage.from_redis(data)
                            await callback(stream_name, message)
                            await self.ack(stream_name, msg_id)
                        except Exception:
                            logger.exception(
                                "redis_message_processing_error",
                                stream=stream_name,
                                msg_id=msg_id,
                            )
            except asyncio.CancelledError:
                break
            except aioredis.ResponseError as e:
                if "NOGROUP" in str(e):
                    logger.warning("redis_nogroup_recreating", streams=streams)
                    for s in streams:
                        await self.create_consumer_group(s)
                else:
                    logger.exception("redis_subscribe_error")
                    await asyncio.sleep(1)
            except Exception:
                logger.exception("redis_subscribe_error")
                await asyncio.sleep(1)

    async def read_latest(self, stream: str) -> StreamMessage | None:
        """XREVRANGE to get latest message from stream."""
        assert self.client is not None
        results = await self.client.xrevrange(stream, count=1)
        if not results:
            return None
        _msg_id, data = results[0]
        return StreamMessage.from_redis(data)

    async def create_consumer_group(self, stream: str) -> None:
        """Create consumer group, ignore if already exists."""
        assert self.client is not None
        try:
            await self.client.xgroup_create(stream, self.consumer_group, id="0", mkstream=True)
            logger.debug("redis_group_created", stream=stream, group=self.consumer_group)
        except aioredis.ResponseError as e:
            if "BUSYGROUP" not in str(e):
                raise

    async def ack(self, stream: str, message_id: str | bytes) -> None:
        """Acknowledge a message."""
        assert self.client is not None
        await self.client.xack(stream, self.consumer_group, message_id)
