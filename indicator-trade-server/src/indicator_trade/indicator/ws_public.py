"""OKX Public WebSocket client wrapper."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable

import structlog

logger = structlog.get_logger()

# Map config timeframes to OKX WS channel names
TF_TO_CHANNEL = {
    "5m": "candle5m",
    "15m": "candle15m",
    "1H": "candle1H",
    "4H": "candle4H",
}


class OKXPublicWS:
    def __init__(self, url: str) -> None:
        self.url = url
        self.connected = False
        self._ws = None
        self._callbacks: dict[str, Callable[[dict], Awaitable[None]]] = {}
        self._reconnect_attempts = 0
        self._max_reconnect_delay = 60
        self._subscriptions: list[dict] = []

    def _create_ws_client(self):
        """Create WsPublicAsync client. Separated for testability."""
        from okx.websocket.WsPublicAsync import WsPublicAsync

        return WsPublicAsync(url=self.url)

    async def connect(self) -> None:
        """Initialize WsPublicAsync, start connection."""
        self._ws = self._create_ws_client()
        await self._ws.start()
        self.connected = True
        logger.info("ws_public_connected", url=self.url)

    async def disconnect(self) -> None:
        """Close WebSocket connection."""
        self.connected = False
        if self._ws is not None:
            try:
                await self._ws.stop()
            except Exception:
                logger.debug("ws_public_stop_error")
            self._ws = None
        logger.info("ws_public_disconnected")

    async def subscribe_candles(
        self,
        instruments: list[str],
        timeframes: list[str],
        callback: Callable[[dict], Awaitable[None]],
    ) -> None:
        """Subscribe to candle channels for given instruments and timeframes."""
        for tf in timeframes:
            channel = TF_TO_CHANNEL.get(tf, f"candle{tf}")
            self._callbacks[channel] = callback
            for inst in instruments:
                sub = {"channel": channel, "instId": inst}
                self._subscriptions.append(sub)
                if self._ws is not None:
                    self._ws.subscribe([sub], self._ws_callback)
        logger.info("ws_subscribed_candles", instruments=instruments, timeframes=timeframes)

    async def subscribe_tickers(
        self,
        instruments: list[str],
        callback: Callable[[dict], Awaitable[None]],
    ) -> None:
        """Subscribe to tickers channel for real-time price."""
        self._callbacks["tickers"] = callback
        for inst in instruments:
            sub = {"channel": "tickers", "instId": inst}
            self._subscriptions.append(sub)
            if self._ws is not None:
                self._ws.subscribe([sub], self._ws_callback)
        logger.info("ws_subscribed_tickers", instruments=instruments)

    async def subscribe_orderbook(
        self,
        instruments: list[str],
        callback: Callable[[dict], Awaitable[None]],
    ) -> None:
        """Subscribe to books5 channel for top 5 order book levels."""
        self._callbacks["books5"] = callback
        for inst in instruments:
            sub = {"channel": "books5", "instId": inst}
            self._subscriptions.append(sub)
            if self._ws is not None:
                self._ws.subscribe([sub], self._ws_callback)
        logger.info("ws_subscribed_orderbook", instruments=instruments)

    async def subscribe_funding(
        self,
        instruments: list[str],
        callback: Callable[[dict], Awaitable[None]],
    ) -> None:
        """Subscribe to funding-rate channel."""
        self._callbacks["funding-rate"] = callback
        for inst in instruments:
            sub = {"channel": "funding-rate", "instId": inst}
            self._subscriptions.append(sub)
            if self._ws is not None:
                self._ws.subscribe([sub], self._ws_callback)
        logger.info("ws_subscribed_funding", instruments=instruments)

    def _ws_callback(self, message: str) -> None:
        """Synchronous callback from python-okx; schedules async routing."""
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(self._on_message(message))
        else:
            asyncio.run(self._on_message(message))

    async def _on_message(self, message: str) -> None:
        """Route incoming WS message to appropriate callback."""
        try:
            data = json.loads(message)
        except (json.JSONDecodeError, TypeError):
            logger.warning("ws_invalid_json", message=str(message)[:200])
            return

        # Skip non-data messages (subscribe confirmations, pongs, etc.)
        if "arg" not in data or "data" not in data:
            return

        channel = data["arg"].get("channel", "")
        callback = self._callbacks.get(channel)
        if callback is not None:
            try:
                await callback(data)
            except Exception:
                logger.exception("ws_callback_error", channel=channel)
        else:
            logger.debug("ws_unhandled_channel", channel=channel)

    async def _reconnect(self) -> None:
        """Auto-reconnect with exponential backoff on disconnect."""
        while True:
            delay = min(2**self._reconnect_attempts, self._max_reconnect_delay)
            logger.info(
                "ws_reconnecting",
                attempt=self._reconnect_attempts + 1,
                delay=delay,
            )
            await asyncio.sleep(delay)
            try:
                await self.connect()
                # Re-subscribe all channels
                if self._ws is not None:
                    for sub in self._subscriptions:
                        self._ws.subscribe([sub], self._ws_callback)
                self._reconnect_attempts = 0
                logger.info("ws_reconnected")
                return
            except Exception:
                self._reconnect_attempts += 1
                logger.exception(
                    "ws_reconnect_failed",
                    attempt=self._reconnect_attempts,
                )
