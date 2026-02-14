"""OKX Private WebSocket wrapper."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

import structlog

logger = structlog.get_logger()


class OKXPrivateWS:
    """OKX Private WebSocket for real-time order/position/account updates."""

    def __init__(
        self, url: str, api_key: str, passphrase: str, secret_key: str
    ) -> None:
        self.url = url
        self.api_key = api_key
        self.passphrase = passphrase
        self.secret_key = secret_key
        self.connected = False

    async def connect(self) -> None:
        """Connect + authenticate with API credentials."""
        ...

    async def disconnect(self) -> None:
        ...

    async def subscribe_orders(
        self, instType: str, callback: Callable[[dict], Awaitable[None]]
    ) -> None:
        """Subscribe {"channel": "orders", "instType": "SWAP"}"""
        ...

    async def subscribe_positions(
        self, instType: str, callback: Callable[[dict], Awaitable[None]]
    ) -> None:
        """Subscribe {"channel": "positions", "instType": "SWAP"}"""
        ...

    async def subscribe_account(
        self, callback: Callable[[dict], Awaitable[None]]
    ) -> None:
        """Subscribe {"channel": "account"}"""
        ...

    def _on_message(self, message: str) -> None:
        ...

    async def _reconnect(self) -> None:
        ...
