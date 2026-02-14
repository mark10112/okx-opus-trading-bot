"""Unit tests for telegram/alerts.py — alert sender."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ui.config import Settings
from ui.models.messages import StreamMessage
from ui.telegram.alerts import AlertSender
from ui.telegram.formatters import MessageFormatter


@pytest.fixture
def settings():
    return Settings(
        TELEGRAM_BOT_TOKEN="test-token",
        TELEGRAM_CHAT_ID="12345",
        ALERT_COOLDOWN_SECONDS=60,
        SILENT_HOURS_UTC=[2, 3, 4],
    )


@pytest.fixture
def formatter():
    return MessageFormatter()


@pytest.fixture
def bot_app():
    app = MagicMock()
    app.bot = MagicMock()
    app.bot.send_message = AsyncMock()
    return app


@pytest.fixture
def sender(bot_app, formatter, settings):
    return AlertSender(
        bot_app=bot_app,
        chat_id="12345",
        formatter=formatter,
        settings=settings,
    )


# ─── _should_alert ───


class TestShouldAlert:
    def test_first_alert_always_allowed(self, sender):
        assert sender._should_alert("trade_fill", "INFO") is True

    def test_cooldown_blocks_repeat(self, sender):
        sender.last_alert_time["trade_fill"] = datetime.now(timezone.utc)
        assert sender._should_alert("trade_fill", "INFO") is False

    def test_critical_bypasses_cooldown(self, sender):
        sender.last_alert_time["system_alert"] = datetime.now(timezone.utc)
        assert sender._should_alert("system_alert", "CRITICAL") is True

    def test_different_type_not_blocked(self, sender):
        sender.last_alert_time["trade_fill"] = datetime.now(timezone.utc)
        assert sender._should_alert("position_update", "INFO") is True

    def test_silent_hours_blocks(self, sender):
        with patch("ui.telegram.alerts.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 1, 15, 3, 0, tzinfo=timezone.utc)
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            assert sender._should_alert("trade_fill", "INFO") is False

    def test_silent_hours_critical_bypasses(self, sender):
        with patch("ui.telegram.alerts.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 1, 15, 3, 0, tzinfo=timezone.utc)
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            assert sender._should_alert("system_alert", "CRITICAL") is True

    def test_outside_silent_hours_allowed(self, sender):
        with patch("ui.telegram.alerts.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc)
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            assert sender._should_alert("trade_fill", "INFO") is True

    def test_no_silent_hours_configured(self, sender):
        sender.settings = Settings(
            TELEGRAM_BOT_TOKEN="t",
            TELEGRAM_CHAT_ID="1",
            SILENT_HOURS_UTC=[],
        )
        assert sender._should_alert("trade_fill", "INFO") is True


# ─── _send ───


class TestSend:
    async def test_sends_message(self, sender, bot_app):
        await sender._send("Hello world", "INFO")
        bot_app.bot.send_message.assert_awaited_once_with(
            chat_id="12345", text="Hello world"
        )

    async def test_logs_error_on_failure(self, sender, bot_app):
        bot_app.bot.send_message.side_effect = Exception("Network error")
        await sender._send("Hello", "INFO")  # should not raise


# ─── Stream handlers ───


class TestOnTradeFill:
    async def test_sends_trade_fill_alert(self, sender, bot_app):
        msg = StreamMessage(
            type="trade_fill",
            payload={
                "symbol": "BTC-USDT-SWAP",
                "direction": "LONG",
                "action": "OPEN_LONG",
                "entry_price": 100000.0,
                "size": 0.01,
            },
        )
        await sender._on_trade_fill(msg)
        bot_app.bot.send_message.assert_awaited_once()
        call_text = bot_app.bot.send_message.call_args.kwargs["text"]
        assert "BTC-USDT-SWAP" in call_text

    async def test_respects_cooldown(self, sender, bot_app):
        sender.last_alert_time["trade_fill"] = datetime.now(timezone.utc)
        msg = StreamMessage(type="trade_fill", payload={"symbol": "BTC"})
        await sender._on_trade_fill(msg)
        bot_app.bot.send_message.assert_not_awaited()


class TestOnPositionUpdate:
    async def test_sends_position_closed_alert(self, sender, bot_app):
        msg = StreamMessage(
            type="position_update",
            payload={
                "symbol": "BTC-USDT-SWAP",
                "direction": "LONG",
                "entry_price": 100000.0,
                "exit_price": 101000.0,
                "pnl_usd": 100.0,
                "pnl_pct": 0.01,
                "duration_seconds": 3600,
                "status": "closed",
            },
        )
        await sender._on_position_update(msg)
        bot_app.bot.send_message.assert_awaited_once()

    async def test_ignores_open_position_update(self, sender, bot_app):
        msg = StreamMessage(
            type="position_update",
            payload={"symbol": "BTC-USDT-SWAP", "status": "open"},
        )
        await sender._on_position_update(msg)
        bot_app.bot.send_message.assert_not_awaited()


class TestOnOpusDecision:
    async def test_sends_decision_alert(self, sender, bot_app):
        msg = StreamMessage(
            type="opus_decision",
            payload={
                "action": "OPEN_LONG",
                "symbol": "BTC-USDT-SWAP",
                "confidence": 0.85,
                "strategy": "momentum",
            },
        )
        await sender._on_opus_decision(msg)
        bot_app.bot.send_message.assert_awaited_once()


class TestOnSystemAlert:
    async def test_sends_critical_alert(self, sender, bot_app):
        msg = StreamMessage(
            type="system_alert",
            payload={
                "severity": "CRITICAL",
                "message": "Max daily loss exceeded",
                "source": "risk_gate",
            },
        )
        await sender._on_system_alert(msg)
        bot_app.bot.send_message.assert_awaited_once()
        call_text = bot_app.bot.send_message.call_args.kwargs["text"]
        assert "CRITICAL" in call_text


class TestOnMarketAlert:
    async def test_sends_market_alert(self, sender, bot_app):
        msg = StreamMessage(
            type="market_alert",
            payload={
                "alert_type": "price_change",
                "symbol": "BTC-USDT-SWAP",
                "message": "Price +3.5%",
                "value": 3.5,
            },
        )
        await sender._on_market_alert(msg)
        bot_app.bot.send_message.assert_awaited_once()


# ─── start_listening routing ───


class TestStartListening:
    async def test_routes_trade_fill(self, sender):
        redis = AsyncMock()

        async def fake_subscribe(streams, callback):
            msg = StreamMessage(
                type="trade_fill",
                payload={"symbol": "BTC-USDT-SWAP", "action": "OPEN_LONG"},
            )
            await callback("trade:fills", msg)

        redis.subscribe = fake_subscribe

        with patch.object(sender, "_on_trade_fill", new_callable=AsyncMock) as mock_handler:
            await sender.start_listening(redis)
            mock_handler.assert_awaited_once()

    async def test_routes_system_alert(self, sender):
        redis = AsyncMock()

        async def fake_subscribe(streams, callback):
            msg = StreamMessage(
                type="system_alert",
                payload={"severity": "CRITICAL", "message": "halt"},
            )
            await callback("system:alerts", msg)

        redis.subscribe = fake_subscribe

        with patch.object(sender, "_on_system_alert", new_callable=AsyncMock) as mock_handler:
            await sender.start_listening(redis)
            mock_handler.assert_awaited_once()
