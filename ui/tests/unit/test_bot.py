"""Unit tests for telegram/bot.py — bot application."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ui.config import Settings
from ui.telegram.bot import TelegramBot


@pytest.fixture
def settings():
    return Settings(
        TELEGRAM_BOT_TOKEN="test-token-123",
        TELEGRAM_CHAT_ID="12345",
        TELEGRAM_ADMIN_IDS=[99999],
    )


@pytest.fixture
def redis():
    r = AsyncMock()
    return r


@pytest.fixture
def db_queries():
    return AsyncMock()


@pytest.fixture
def bot(settings, redis, db_queries):
    return TelegramBot(settings=settings, redis=redis, db_queries=db_queries)


# ─── _check_authorized ───


class TestCheckAuthorized:
    def test_authorized_chat(self, bot):
        update = MagicMock()
        update.effective_chat.id = 12345
        assert bot._check_authorized(update) is True

    def test_unauthorized_chat(self, bot):
        update = MagicMock()
        update.effective_chat.id = 99999999
        assert bot._check_authorized(update) is False

    def test_string_comparison(self, bot):
        update = MagicMock()
        update.effective_chat.id = 12345
        bot.settings.TELEGRAM_CHAT_ID = "12345"
        assert bot._check_authorized(update) is True


# ─── _setup_handlers ───


class TestSetupHandlers:
    def test_registers_all_commands(self, bot):
        mock_app = MagicMock()
        bot.app = mock_app

        bot._setup_handlers()

        assert mock_app.add_handler.call_count == 10

    def test_handler_commands_are_correct(self, bot):
        mock_app = MagicMock()
        bot.app = mock_app

        bot._setup_handlers()

        registered_commands = set()
        for call in mock_app.add_handler.call_args_list:
            handler = call.args[0]
            for cmd in handler.commands:
                registered_commands.add(cmd)

        expected = {
            "status", "positions", "trades", "performance",
            "playbook", "halt", "resume", "research", "reflect", "config",
        }
        assert registered_commands == expected


# ─── start / stop lifecycle ───


class TestLifecycle:
    @patch("ui.telegram.bot.Application")
    async def test_start_builds_app(self, mock_app_cls, bot):
        mock_builder = MagicMock()
        mock_app_instance = MagicMock()
        mock_app_instance.initialize = AsyncMock()
        mock_app_instance.start = AsyncMock()
        mock_app_instance.updater = MagicMock()
        mock_app_instance.updater.start_polling = AsyncMock()
        mock_app_instance.updater.stop = AsyncMock()
        mock_app_instance.stop = AsyncMock()
        mock_app_instance.shutdown = AsyncMock()
        mock_app_instance.add_handler = MagicMock()

        mock_builder.token.return_value = mock_builder
        mock_builder.build.return_value = mock_app_instance
        mock_app_cls.builder.return_value = mock_builder

        # Make start_listening complete immediately
        bot.redis.subscribe = AsyncMock()

        # Start bot (will set up app and handlers)
        start_task = bot.start()

        # We need to stop it after it starts
        import asyncio
        async def stop_after_delay():
            await asyncio.sleep(0.1)
            await bot.stop()

        await asyncio.gather(start_task, stop_after_delay())

        mock_app_instance.initialize.assert_awaited_once()
        mock_app_instance.start.assert_awaited_once()
        mock_app_instance.updater.start_polling.assert_awaited_once()

    @patch("ui.telegram.bot.Application")
    async def test_stop_shuts_down(self, mock_app_cls, bot):
        mock_app_instance = MagicMock()
        mock_app_instance.updater = MagicMock()
        mock_app_instance.updater.stop = AsyncMock()
        mock_app_instance.stop = AsyncMock()
        mock_app_instance.shutdown = AsyncMock()
        bot.app = mock_app_instance
        bot._running = True

        await bot.stop()

        mock_app_instance.updater.stop.assert_awaited_once()
        mock_app_instance.stop.assert_awaited_once()
        mock_app_instance.shutdown.assert_awaited_once()

    async def test_stop_without_app_is_safe(self, bot):
        bot.app = None
        await bot.stop()  # should not raise
