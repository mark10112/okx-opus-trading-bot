"""OKX Public WebSocket client wrapper."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

import structlog

logger = structlog.get_logger()


class OKXPublicWS:
    def __init__(self, url: str) -> None:
        self.url = url
        self.connected = False

    async def connect(self) -> None:
        """Initialize WsPublicAsync, start connection."""
        ...

    async def disconnect(self) -> None:
        """Close WebSocket connection."""
        ...

    async def subscribe_candles(
        self,
        instruments: list[str],
        timeframes: list[str],
        callback: Callable[[dict], Awaitable[None]],
    ) -> None:
        """Subscribe to candle channels for given instruments and timeframes."""
        ...

    async def subscribe_tickers(
        self,
        instruments: list[str],
        callback: Callable[[dict], Awaitable[None]],
    ) -> None:
        """Subscribe to tickers channel for real-time price."""
        ...

    async def subscribe_orderbook(
        self,
        instruments: list[str],
        callback: Callable[[dict], Awaitable[None]],
    ) -> None:
        """Subscribe to books5 channel for top 5 order book levels."""
        ...

    async def subscribe_funding(
        self,
        instruments: list[str],
        callback: Callable[[dict], Awaitable[None]],
    ) -> None:
        """Subscribe to funding-rate channel."""
        ...

    def _on_message(self, message: str) -> None:
        """Route incoming WS message to appropriate callback."""
        ...

    async def _reconnect(self) -> None:
        """Auto-reconnect with exponential backoff on disconnect."""
        ...
