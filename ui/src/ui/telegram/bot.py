"""Application builder + handlers setup."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import structlog
from telegram.ext import Application, CommandHandler

from ui.telegram.alerts import AlertSender
from ui.telegram.commands import CommandHandler as CmdHandler
from ui.telegram.formatters import MessageFormatter

if TYPE_CHECKING:
    from ui.config import Settings
    from ui.db.queries import DBQueries
    from ui.redis_client import RedisClient

logger = structlog.get_logger()


class TelegramBot:
    def __init__(
        self,
        settings: Settings,
        redis: RedisClient,
        db_queries: DBQueries,
    ) -> None:
        self.settings = settings
        self.redis = redis
        self.db_queries = db_queries
        self.app: Application | None = None
        self._running = False
        self._alert_task: asyncio.Task | None = None

    async def start(self) -> None:
        """
        1. Build Application with bot token
        2. Register command handlers
        3. Start alert listener (Redis subscriber)
        4. Start polling for Telegram updates
        """
        self.app = Application.builder().token(self.settings.TELEGRAM_BOT_TOKEN).build()
        self._setup_handlers()

        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling()

        self._running = True
        logger.info("telegram_bot_started")

        formatter = MessageFormatter()
        alert_sender = AlertSender(
            bot_app=self.app,
            chat_id=self.settings.TELEGRAM_CHAT_ID,
            formatter=formatter,
            settings=self.settings,
        )
        self._alert_task = asyncio.create_task(alert_sender.start_listening(self.redis))

        try:
            while self._running:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass

    async def stop(self) -> None:
        """Gracefully stop bot + alert listener."""
        self._running = False

        if self._alert_task and not self._alert_task.done():
            self._alert_task.cancel()
            try:
                await self._alert_task
            except asyncio.CancelledError:
                pass

        if self.app:
            await self.app.updater.stop()
            await self.app.stop()
            await self.app.shutdown()
            logger.info("telegram_bot_stopped")

    def _setup_handlers(self) -> None:
        """Register all command handlers."""
        formatter = MessageFormatter()
        cmd = CmdHandler(
            db=self.db_queries,
            redis=self.redis,
            formatter=formatter,
            settings=self.settings,
        )

        commands = [
            ("status", cmd.cmd_status),
            ("positions", cmd.cmd_positions),
            ("trades", cmd.cmd_trades),
            ("performance", cmd.cmd_performance),
            ("playbook", cmd.cmd_playbook),
            ("halt", cmd.cmd_halt),
            ("resume", cmd.cmd_resume),
            ("research", cmd.cmd_research),
            ("reflect", cmd.cmd_reflect),
            ("config", cmd.cmd_config),
        ]

        for name, callback in commands:
            self.app.add_handler(CommandHandler(name, callback))

    def _check_authorized(self, update) -> bool:
        """Check if message comes from authorized chat_id."""
        chat_id = str(update.effective_chat.id)
        return chat_id == self.settings.TELEGRAM_CHAT_ID
