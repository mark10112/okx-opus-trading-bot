"""OKX Private WebSocket wrapper."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable

import structlog

logger = structlog.get_logger()


class OKXPrivateWS:
    """OKX Private WebSocket for real-time order/position/account updates."""

    def __init__(self, url: str, api_key: str, passphrase: str, secret_key: str) -> None:
        self.url = url
        self.api_key = api_key
        self.passphrase = passphrase
        self.secret_key = secret_key
        self.connected = False
        self._ws = None
        self._callbacks: dict[str, Callable[[dict], Awaitable[None]]] = {}
        self._reconnect_attempts = 0
        self._max_reconnect_delay = 60
        self._subscriptions: list[dict] = []

    def _create_ws_client(self):
        """Create WsPrivateAsync client. Separated for testability."""
        from okx.websocket.WsPrivateAsync import WsPrivateAsync

        return WsPrivateAsync(
            apiKey=self.api_key,
            passphrase=self.passphrase,
            secretKey=self.secret_key,
            url=self.url,
        )

    async def connect(self) -> None:
        """Connect + authenticate with API credentials."""
        self._ws = self._create_ws_client()
        await self._ws.start()
        self.connected = True
        logger.info("ws_private_connected", url=self.url)

    async def disconnect(self) -> None:
        """Close WebSocket connection."""
        self.connected = False
        if self._ws is not None:
            try:
                await self._ws.stop()
            except Exception:
                logger.debug("ws_private_stop_error")
            self._ws = None
        logger.info("ws_private_disconnected")

    async def subscribe_orders(
        self, instType: str, callback: Callable[[dict], Awaitable[None]]
    ) -> None:
        """Subscribe {"channel": "orders", "instType": "SWAP"}"""
        self._callbacks["orders"] = callback
        sub = {"channel": "orders", "instType": instType}
        self._subscriptions.append(sub)
        if self._ws is not None:
            self._ws.subscribe([sub], self._ws_callback)
        logger.info("ws_subscribed_orders", instType=instType)

    async def subscribe_positions(
        self, instType: str, callback: Callable[[dict], Awaitable[None]]
    ) -> None:
        """Subscribe {"channel": "positions", "instType": "SWAP"}"""
        self._callbacks["positions"] = callback
        sub = {"channel": "positions", "instType": instType}
        self._subscriptions.append(sub)
        if self._ws is not None:
            self._ws.subscribe([sub], self._ws_callback)
        logger.info("ws_subscribed_positions", instType=instType)

    async def subscribe_account(self, callback: Callable[[dict], Awaitable[None]]) -> None:
        """Subscribe {"channel": "account"}"""
        self._callbacks["account"] = callback
        sub = {"channel": "account"}
        self._subscriptions.append(sub)
        if self._ws is not None:
            self._ws.subscribe([sub], self._ws_callback)
        logger.info("ws_subscribed_account")

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
            logger.warning("ws_private_invalid_json", message=str(message)[:200])
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
                logger.exception("ws_private_callback_error", channel=channel)
        else:
            logger.debug("ws_private_unhandled_channel", channel=channel)

    def _get_reconnect_delay(self) -> int:
        """Calculate reconnect delay with exponential backoff."""
        return min(2**self._reconnect_attempts, self._max_reconnect_delay)

    async def _reconnect(self) -> None:
        """Auto-reconnect with exponential backoff on disconnect."""
        delay = self._get_reconnect_delay()
        logger.info(
            "ws_private_reconnecting",
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
            logger.info("ws_private_reconnected")
        except Exception:
            self._reconnect_attempts += 1
            logger.exception(
                "ws_private_reconnect_failed",
                attempt=self._reconnect_attempts,
            )
