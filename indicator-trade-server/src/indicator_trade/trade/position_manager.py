"""Track positions, detect closes."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

import structlog

from indicator_trade.models.messages import PositionUpdateMessage
from indicator_trade.models.position import Position

if TYPE_CHECKING:
    from indicator_trade.redis_client import RedisClient

logger = structlog.get_logger()


class PositionManager:
    """Track open positions in memory, updated via OKX Private WebSocket."""

    def __init__(self, redis: RedisClient) -> None:
        self.redis = redis
        self.positions: dict[str, Position] = {}

    async def update(self, data: dict) -> Position:
        """Parse OKX position update, update internal state, publish to Redis."""
        instId = data.get("instId", "")
        posSide = data.get("posSide", "")
        key = f"{instId}:{posSide}"

        utime = None
        if data.get("uTime"):
            utime = datetime.fromtimestamp(int(data["uTime"]) / 1000, tz=timezone.utc)

        position = Position(
            instId=instId,
            posSide=posSide,
            pos=float(data.get("pos", 0)),
            avgPx=float(data.get("avgPx", 0)),
            upl=float(data.get("upl", 0)),
            uplRatio=float(data.get("uplRatio", 0)),
            lever=float(data.get("lever", 1)),
            liqPx=float(data.get("liqPx", 0)),
            margin=float(data.get("margin", 0)),
            mgnRatio=float(data.get("mgnRatio", 0)),
            uTime=utime,
        )

        is_closed = self.is_position_closed(data)

        if is_closed:
            self.positions.pop(key, None)
            logger.info("position_closed", instId=instId, posSide=posSide)
        else:
            self.positions[key] = position
            logger.info(
                "position_updated",
                instId=instId,
                posSide=posSide,
                pos=position.pos,
                avgPx=position.avgPx,
            )

        # Publish update to Redis
        payload = position.model_dump(mode="json")
        payload["closed"] = is_closed
        msg = PositionUpdateMessage(payload=payload)
        await self.redis.publish("trade:positions", msg)

        return position

    def get_all(self) -> list[Position]:
        """Get all current positions."""
        return list(self.positions.values())

    def get(self, instId: str, posSide: str) -> Position | None:
        """Get specific position by instrument and side."""
        return self.positions.get(f"{instId}:{posSide}")

    def is_position_closed(self, data: dict) -> bool:
        """Check if position update indicates close (pos == '0' or empty)."""
        pos = data.get("pos", None)
        if pos is None:
            return False
        if pos == "" or pos == "0":
            return True
        try:
            return float(pos) == 0.0
        except (ValueError, TypeError):
            return False
