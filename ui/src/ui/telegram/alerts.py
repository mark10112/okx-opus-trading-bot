"""Auto-alert sender (Redis subscriber)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from ui.config import Settings
    from ui.models.messages import StreamMessage
    from ui.redis_client import RedisClient
    from ui.telegram.formatters import MessageFormatter

logger = structlog.get_logger()

ALERT_STREAMS = [
    "trade:fills",
    "trade:positions",
    "opus:decisions",
    "system:alerts",
    "market:alerts",
]

STREAM_HANDLER_MAP = {
    "trade:fills": "_on_trade_fill",
    "trade:positions": "_on_position_update",
    "opus:decisions": "_on_opus_decision",
    "system:alerts": "_on_system_alert",
    "market:alerts": "_on_market_alert",
}


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

        async def _route(stream_name: str, message: StreamMessage) -> None:
            handler_name = STREAM_HANDLER_MAP.get(stream_name)
            if handler_name:
                handler = getattr(self, handler_name)
                await handler(message)
            else:
                logger.warning("alert_unknown_stream", stream=stream_name)

        await redis.subscribe(ALERT_STREAMS, _route)

    async def _on_trade_fill(self, message: StreamMessage) -> None:
        if not self._should_alert("trade_fill", "INFO"):
            return
        text = self.formatter.format_trade_fill(message.payload)
        await self._send(text, "INFO")
        self.last_alert_time["trade_fill"] = datetime.now(timezone.utc)

    async def _on_position_update(self, message: StreamMessage) -> None:
        if message.payload.get("status") != "closed":
            return
        if not self._should_alert("position_update", "INFO"):
            return
        text = self.formatter.format_position_closed(message.payload)
        await self._send(text, "INFO")
        self.last_alert_time["position_update"] = datetime.now(timezone.utc)

    async def _on_opus_decision(self, message: StreamMessage) -> None:
        if not self._should_alert("opus_decision", "INFO"):
            return
        payload = message.payload
        text = (
            f"🧠 Opus Decision\n"
            f"Action: {payload.get('action', 'N/A')}\n"
            f"Symbol: {payload.get('symbol', 'N/A')}\n"
            f"Confidence: {payload.get('confidence', 0):.0%}\n"
            f"Strategy: {payload.get('strategy', 'N/A')}"
        )
        await self._send(text, "INFO")
        self.last_alert_time["opus_decision"] = datetime.now(timezone.utc)

    async def _on_system_alert(self, message: StreamMessage) -> None:
        severity = message.payload.get("severity", "INFO")
        if not self._should_alert("system_alert", severity):
            return
        text = self.formatter.format_system_alert(message.payload)
        await self._send(text, severity)
        self.last_alert_time["system_alert"] = datetime.now(timezone.utc)

    async def _on_market_alert(self, message: StreamMessage) -> None:
        if not self._should_alert("market_alert", "WARNING"):
            return
        text = self.formatter.format_market_alert(message.payload)
        await self._send(text, "WARNING")
        self.last_alert_time["market_alert"] = datetime.now(timezone.utc)

    async def _send(self, text: str, severity: str = "INFO") -> None:
        """Send formatted message to Telegram chat."""
        try:
            await self.bot_app.bot.send_message(chat_id=self.chat_id, text=text)
        except Exception:
            logger.exception("telegram_send_error", severity=severity)

    def _should_alert(self, alert_type: str, severity: str) -> bool:
        """Check cooldown, silent hours. CRITICAL always sends."""
        if severity == "CRITICAL":
            return True

        now = datetime.now(timezone.utc)

        if self.settings.SILENT_HOURS_UTC and now.hour in self.settings.SILENT_HOURS_UTC:
            return False

        last = self.last_alert_time.get(alert_type)
        if last is not None:
            cooldown = timedelta(seconds=self.settings.ALERT_COOLDOWN_SECONDS)
            if now - last < cooldown:
                return False

        return True
