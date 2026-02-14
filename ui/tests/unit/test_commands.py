"""Unit tests for telegram/commands.py — command handlers."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ui.config import Settings
from ui.telegram.commands import CommandHandler
from ui.telegram.formatters import MessageFormatter


@pytest.fixture
def settings():
    return Settings(
        TELEGRAM_BOT_TOKEN="test-token",
        TELEGRAM_CHAT_ID="12345",
        TELEGRAM_ADMIN_IDS=[99999],
        ALERT_COOLDOWN_SECONDS=60,
    )


@pytest.fixture
def db():
    return AsyncMock()


@pytest.fixture
def redis():
    return AsyncMock()


@pytest.fixture
def formatter():
    return MessageFormatter()


@pytest.fixture
def handler(db, redis, formatter, settings):
    return CommandHandler(db=db, redis=redis, formatter=formatter, settings=settings)


def _make_update(chat_id=12345, text="/status", args=None):
    """Create a mock Telegram Update object."""
    update = MagicMock()
    update.effective_chat.id = chat_id
    update.effective_user.id = chat_id
    update.message = MagicMock()
    update.message.reply_text = AsyncMock()
    context = MagicMock()
    context.args = args or []
    return update, context


# ─── Auth check ───


class TestAuthCheck:
    async def test_authorized_user(self, handler):
        update, context = _make_update(chat_id=12345)
        handler.db.get_equity_and_pnl.return_value = (100000.0, 0.0)
        handler.db.get_open_positions.return_value = []
        handler.db.get_latest_decision.return_value = None
        handler.db.get_screener_pass_rate.return_value = 0.0
        await handler.cmd_status(update, context)
        update.message.reply_text.assert_awaited_once()

    async def test_unauthorized_user(self, handler):
        update, context = _make_update(chat_id=99999999)
        await handler.cmd_status(update, context)
        call_text = update.message.reply_text.call_args.args[0]
        assert "unauthorized" in call_text.lower() or "not authorized" in call_text.lower()


# ─── /status ───


class TestCmdStatus:
    async def test_returns_status(self, handler):
        update, context = _make_update()
        handler.db.get_equity_and_pnl.return_value = (105000.0, 500.0)
        handler.db.get_open_positions.return_value = [{"symbol": "BTC-USDT-SWAP"}]
        handler.db.get_latest_decision.return_value = {"strategy": "momentum", "confidence": 0.8}
        handler.db.get_screener_pass_rate.return_value = 0.2

        await handler.cmd_status(update, context)

        call_text = update.message.reply_text.call_args.args[0]
        assert "105,000.00" in call_text
        assert "500.00" in call_text

    async def test_handles_db_error(self, handler):
        update, context = _make_update()
        handler.db.get_equity_and_pnl.side_effect = Exception("DB error")

        await handler.cmd_status(update, context)

        call_text = update.message.reply_text.call_args.args[0]
        assert "error" in call_text.lower()


# ─── /positions ───


class TestCmdPositions:
    async def test_with_positions(self, handler):
        update, context = _make_update()
        handler.db.get_open_positions.return_value = [
            {
                "symbol": "BTC-USDT-SWAP",
                "direction": "LONG",
                "entry_price": 100000.0,
                "size": 0.01,
                "leverage": 2.0,
                "pnl_usd": 150.0,
                "stop_loss": 98000.0,
                "take_profit": 105000.0,
            }
        ]

        await handler.cmd_positions(update, context)

        call_text = update.message.reply_text.call_args.args[0]
        assert "BTC-USDT-SWAP" in call_text

    async def test_no_positions(self, handler):
        update, context = _make_update()
        handler.db.get_open_positions.return_value = []

        await handler.cmd_positions(update, context)

        call_text = update.message.reply_text.call_args.args[0]
        assert "no" in call_text.lower()


# ─── /trades ───


class TestCmdTrades:
    async def test_default_limit(self, handler):
        update, context = _make_update(args=[])
        handler.db.get_recent_trades.return_value = [
            {
                "trade_id": "t-001",
                "symbol": "BTC-USDT-SWAP",
                "direction": "LONG",
                "pnl_usd": 50.0,
                "strategy_used": "momentum",
            }
        ]

        await handler.cmd_trades(update, context)

        handler.db.get_recent_trades.assert_awaited_once_with(limit=10)
        update.message.reply_text.assert_awaited_once()

    async def test_custom_limit(self, handler):
        update, context = _make_update(args=["5"])
        handler.db.get_recent_trades.return_value = []

        await handler.cmd_trades(update, context)

        handler.db.get_recent_trades.assert_awaited_once_with(limit=5)

    async def test_invalid_limit_uses_default(self, handler):
        update, context = _make_update(args=["abc"])
        handler.db.get_recent_trades.return_value = []

        await handler.cmd_trades(update, context)

        handler.db.get_recent_trades.assert_awaited_once_with(limit=10)


# ─── /performance ───


class TestCmdPerformance:
    async def test_returns_performance(self, handler):
        update, context = _make_update()
        handler.db.get_performance_metrics.return_value = {
            "total_trades": 50,
            "wins": 35,
            "losses": 15,
            "win_rate": 0.7,
            "total_pnl": 1500.0,
            "profit_factor": 3.5,
            "avg_pnl": 30.0,
        }

        await handler.cmd_performance(update, context)

        call_text = update.message.reply_text.call_args.args[0]
        assert "50" in call_text
        assert "1,500.00" in call_text


# ─── /playbook ───


class TestCmdPlaybook:
    async def test_returns_playbook(self, handler):
        update, context = _make_update()
        handler.db.get_latest_playbook.return_value = {
            "version": 5,
            "playbook_json": {
                "regime_rules": {"trending_up": {"strategies": ["momentum"]}},
                "lessons": ["Cut losses early"],
            },
            "change_summary": "Updated",
            "triggered_by": "reflection",
        }

        await handler.cmd_playbook(update, context)

        call_text = update.message.reply_text.call_args.args[0]
        assert "5" in call_text

    async def test_no_playbook(self, handler):
        update, context = _make_update()
        handler.db.get_latest_playbook.return_value = {}

        await handler.cmd_playbook(update, context)

        call_text = update.message.reply_text.call_args.args[0]
        assert "no" in call_text.lower()


# ─── /halt (admin only) ───


class TestCmdHalt:
    async def test_admin_can_halt(self, handler):
        update, context = _make_update(chat_id=99999, args=["emergency"])
        # admin user (99999 is in TELEGRAM_ADMIN_IDS)
        # but chat_id must also be authorized for the bot
        handler.settings.TELEGRAM_CHAT_ID = "99999"

        await handler.cmd_halt(update, context)

        update.message.reply_text.assert_awaited_once()
        call_text = update.message.reply_text.call_args.args[0]
        assert "halt" in call_text.lower()
        handler.redis.publish.assert_awaited_once()

    async def test_non_admin_rejected(self, handler):
        update, context = _make_update(chat_id=12345, args=["test"])
        # 12345 is authorized chat but NOT in admin_ids

        await handler.cmd_halt(update, context)

        call_text = update.message.reply_text.call_args.args[0]
        assert "admin" in call_text.lower()
        handler.redis.publish.assert_not_awaited()


# ─── /resume (admin only) ───


class TestCmdResume:
    async def test_admin_can_resume(self, handler):
        update, context = _make_update(chat_id=99999)
        handler.settings.TELEGRAM_CHAT_ID = "99999"

        await handler.cmd_resume(update, context)

        update.message.reply_text.assert_awaited_once()
        call_text = update.message.reply_text.call_args.args[0]
        assert "resum" in call_text.lower()
        handler.redis.publish.assert_awaited_once()

    async def test_non_admin_rejected(self, handler):
        update, context = _make_update(chat_id=12345)

        await handler.cmd_resume(update, context)

        call_text = update.message.reply_text.call_args.args[0]
        assert "admin" in call_text.lower()


# ─── /research ───


class TestCmdResearch:
    async def test_publishes_research_request(self, handler):
        update, context = _make_update(args=["BTC", "outlook"])

        await handler.cmd_research(update, context)

        update.message.reply_text.assert_awaited_once()
        handler.redis.publish.assert_awaited_once()

    async def test_no_query_provided(self, handler):
        update, context = _make_update(args=[])

        await handler.cmd_research(update, context)

        call_text = update.message.reply_text.call_args.args[0]
        assert "usage" in call_text.lower() or "query" in call_text.lower()
        handler.redis.publish.assert_not_awaited()


# ─── /reflect ───


class TestCmdReflect:
    async def test_publishes_reflect_request(self, handler):
        update, context = _make_update()

        await handler.cmd_reflect(update, context)

        update.message.reply_text.assert_awaited_once()
        handler.redis.publish.assert_awaited_once()


# ─── /config ───


class TestCmdConfig:
    async def test_view_config(self, handler):
        update, context = _make_update(args=[])

        await handler.cmd_config(update, context)

        call_text = update.message.reply_text.call_args.args[0]
        assert "cooldown" in call_text.lower() or "config" in call_text.lower()

    async def test_admin_set_config(self, handler):
        update, context = _make_update(chat_id=99999, args=["cooldown", "120"])
        handler.settings.TELEGRAM_CHAT_ID = "99999"

        await handler.cmd_config(update, context)

        call_text = update.message.reply_text.call_args.args[0]
        assert "120" in call_text or "updated" in call_text.lower()

    async def test_non_admin_set_rejected(self, handler):
        update, context = _make_update(chat_id=12345, args=["cooldown", "120"])

        await handler.cmd_config(update, context)

        call_text = update.message.reply_text.call_args.args[0]
        assert "admin" in call_text.lower()
