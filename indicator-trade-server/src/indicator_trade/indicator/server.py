"""Indicator server main loop: WebSocket data collection + snapshot publishing."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from indicator_trade.config import Settings
    from indicator_trade.redis_client import RedisClient

logger = structlog.get_logger()


class IndicatorServer:
    def __init__(self, settings: Settings, redis: RedisClient) -> None:
        self.settings = settings
        self.redis = redis
        self.running = False

    async def start(self) -> None:
        """
        1. Backfill historical candles from REST API (200 candles per TF)
        2. Subscribe WebSocket channels
        3. Start snapshot_loop (publish every SNAPSHOT_INTERVAL_SECONDS)
        """
        ...

    async def stop(self) -> None:
        """Gracefully close WebSocket connections, flush pending DB writes."""
        self.running = False
