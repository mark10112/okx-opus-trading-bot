"""Auto-alert sender (Redis subscriber)."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from ui.config import Settings
    from ui.redis_client import RedisClient
    from ui.telegram.formatters import MessageFormatter

logger = structlog.get_logger()


class AlertSender:
    """Listens to Redis Streams and sends Telegram notifications."""

    def __init__(
        self,
        bot_app: object,
        chat_id: str,
        formatter: MessageFormatter,
        settings: Settings,
    ) -> None:
        self.bot_app = bot_app
        self.chat_id = chat_id
        self.formatter = formatter
        self.settings = settings
        self.last_alert_time: dict[str, datetime] = {}

    async def start_listening(self, redis: RedisClient) -> None:
        """Subscribe to multiple Redis streams and route to handlers."""
        ...

    async def _on_trade_fill(self, message: dict) -> None:
        ...

    async def _on_position_update(self, message: dict) -> None:
        ...

    async def _on_opus_decision(self, message: dict) -> None:
        ...

    async def _on_system_alert(self, message: dict) -> None:
        ...

    async def _on_market_alert(self, message: dict) -> None:
        ...

    async def _send(self, text: str, severity: str = "INFO") -> None:
        """Send formatted message to Telegram chat."""
        ...

    def _should_alert(self, alert_type: str, severity: str) -> bool:
        """Check cooldown, silent hours. CRITICAL always sends."""
        ...
