"""Redis Stream message schemas (shared protocol).

This file is identical across all 3 repos to ensure consistent serialization.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from pydantic import BaseModel, Field


class StreamMessage(BaseModel):
    """Base message for all Redis Stream communications."""

    msg_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source: str = ""
    type: str = ""
    payload: dict = {}
    metadata: dict = {}

    def to_redis(self) -> dict[str, str]:
        """Serialize to flat dict for XADD."""
        return {"data": self.model_dump_json()}

    @classmethod
    def from_redis(cls, data: dict[bytes | str, bytes | str]) -> StreamMessage:
        """Deserialize from Redis XREADGROUP result."""
        raw = data.get(b"data") or data.get("data")
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        return cls.model_validate_json(raw)


class MarketSnapshotMessage(StreamMessage):
    """Published by indicator server to market:snapshots."""

    source: str = "indicator_server"
    type: str = "market_snapshot"


class MarketAlertMessage(StreamMessage):
    """Published by indicator server to market:alerts."""

    source: str = "indicator_server"
    type: str = "market_alert"


class TradeFillMessage(StreamMessage):
    """Published by trade server to trade:fills."""

    source: str = "trade_server"
    type: str = "trade_fill"


class PositionUpdateMessage(StreamMessage):
    """Published by trade server to trade:positions."""

    source: str = "trade_server"
    type: str = "position_update"


class TradeOrderMessage(StreamMessage):
    """Published by orchestrator to trade:orders."""

    source: str = "orchestrator"
    type: str = "trade_order"


class OpusDecisionMessage(StreamMessage):
    """Published by orchestrator to opus:decisions."""

    source: str = "orchestrator"
    type: str = "opus_decision"


class SystemAlertMessage(StreamMessage):
    """Published to system:alerts by any component."""

    type: str = "system_alert"
