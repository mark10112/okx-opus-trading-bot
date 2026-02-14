"""Track positions, detect closes."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from indicator_trade.models.position import Position
    from indicator_trade.redis_client import RedisClient

logger = structlog.get_logger()


class PositionManager:
    """Track open positions in memory, updated via OKX Private WebSocket."""

    def __init__(self, redis: RedisClient) -> None:
        self.redis = redis
        self.positions: dict[str, Position] = {}

    async def update(self, data: dict) -> Position:
        """Parse OKX position update, update internal state, publish to Redis."""
        ...

    def get_all(self) -> list[Position]:
        """Get all current positions."""
        ...

    def get(self, instId: str, posSide: str) -> Position | None:
        """Get specific position by instrument and side."""
        ...

    def is_position_closed(self, data: dict) -> bool:
        """Check if position update indicates close (pos == '0')."""
        ...
