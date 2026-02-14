"""Trade server main loop: Redis subscriber + order execution."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from indicator_trade.config import Settings
    from indicator_trade.redis_client import RedisClient

logger = structlog.get_logger()


class TradeServer:
    def __init__(self, settings: Settings, redis: RedisClient) -> None:
        self.settings = settings
        self.redis = redis
        self.running = False

    async def start(self) -> None:
        """
        1. Initialize OKX REST client
        2. Connect OKX Private WebSocket
        3. Subscribe to orders, positions, account channels
        4. Subscribe Redis "trade:orders" for incoming commands
        5. Set leverage for all instruments
        """
        ...

    async def stop(self) -> None:
        """Close all connections."""
        self.running = False

    async def _on_trade_order(self, stream: str, message: dict) -> None:
        """Redis subscriber callback for trade:orders."""
        ...

    async def _on_order_update(self, data: dict) -> None:
        """OKX Private WS callback for orders channel."""
        ...

    async def _on_position_update(self, data: dict) -> None:
        """OKX Private WS callback for positions channel."""
        ...

    async def _on_account_update(self, data: dict) -> None:
        """OKX Private WS callback for account channel."""
        ...
