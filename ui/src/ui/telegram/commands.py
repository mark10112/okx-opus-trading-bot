"""All /command handlers."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from ui.models.messages import SystemAlertMessage

if TYPE_CHECKING:
    from ui.config import Settings
    from ui.db.queries import DBQueries
    from ui.redis_client import RedisClient
    from ui.telegram.formatters import MessageFormatter

logger = structlog.get_logger()


class CommandHandler:
    def __init__(
        self,
        db: DBQueries,
        redis: RedisClient,
        formatter: MessageFormatter,
        settings: Settings,
    ) -> None:
        self.db = db
        self.redis = redis
        self.formatter = formatter
        self.settings = settings

    def _is_authorized(self, update) -> bool:
        """Check if message comes from authorized chat_id."""
        chat_id = str(update.effective_chat.id)
        return chat_id == self.settings.TELEGRAM_CHAT_ID

    def _is_admin(self, update) -> bool:
        """Check if user is in admin list."""
        user_id = update.effective_user.id
        return user_id in self.settings.TELEGRAM_ADMIN_IDS

    async def cmd_status(self, update, context) -> None:
        """/status — equity, PnL, positions, bot state, screener rate."""
        if not self._is_authorized(update):
            await update.message.reply_text("⛔ Not authorized")
            return
        try:
            equity, pnl = await self.db.get_equity_and_pnl()
            positions = await self.db.get_open_positions()
            decision = await self.db.get_latest_decision()
            screener_rate = await self.db.get_screener_pass_rate()
            text = self.formatter.format_status(
                equity=equity,
                daily_pnl=pnl,
                positions=positions,
                state="RUNNING",
                last_decision=decision,
                screener_rate=screener_rate,
            )
            await update.message.reply_text(text)
        except Exception:
            logger.exception("cmd_status_error")
            await update.message.reply_text("❌ Error fetching status")

    async def cmd_positions(self, update, context) -> None:
        """/positions — detailed open positions."""
        if not self._is_authorized(update):
            await update.message.reply_text("⛔ Not authorized")
            return
        try:
            positions = await self.db.get_open_positions()
            text = self.formatter.format_positions(positions)
            await update.message.reply_text(text)
        except Exception:
            logger.exception("cmd_positions_error")
            await update.message.reply_text("❌ Error fetching positions")

    async def cmd_trades(self, update, context) -> None:
        """/trades [n=10] — last N closed trades."""
        if not self._is_authorized(update):
            await update.message.reply_text("⛔ Not authorized")
            return
        try:
            limit = 10
            if context.args:
                try:
                    limit = int(context.args[0])
                except ValueError:
                    pass
            trades = await self.db.get_recent_trades(limit=limit)
            text = self.formatter.format_trades_list(trades)
            await update.message.reply_text(text)
        except Exception:
            logger.exception("cmd_trades_error")
            await update.message.reply_text("❌ Error fetching trades")

    async def cmd_performance(self, update, context) -> None:
        """/performance — win rate, Sharpe, PnL, breakdowns."""
        if not self._is_authorized(update):
            await update.message.reply_text("⛔ Not authorized")
            return
        try:
            metrics = await self.db.get_performance_metrics()
            text = self.formatter.format_performance(metrics)
            await update.message.reply_text(text)
        except Exception:
            logger.exception("cmd_performance_error")
            await update.message.reply_text("❌ Error fetching performance")

    async def cmd_playbook(self, update, context) -> None:
        """/playbook — current playbook summary."""
        if not self._is_authorized(update):
            await update.message.reply_text("⛔ Not authorized")
            return
        try:
            playbook = await self.db.get_latest_playbook()
            text = self.formatter.format_playbook(playbook)
            await update.message.reply_text(text)
        except Exception:
            logger.exception("cmd_playbook_error")
            await update.message.reply_text("❌ Error fetching playbook")

    async def cmd_halt(self, update, context) -> None:
        """/halt [reason] — emergency halt (admin only)."""
        if not self._is_authorized(update):
            await update.message.reply_text("⛔ Not authorized")
            return
        if not self._is_admin(update):
            await update.message.reply_text("⛔ Admin only command")
            return
        reason = " ".join(context.args) if context.args else "Manual halt via Telegram"
        msg = SystemAlertMessage(
            source="telegram",
            payload={"severity": "CRITICAL", "message": f"HALT: {reason}", "action": "halt"},
        )
        await self.redis.publish("system:alerts", msg)
        await update.message.reply_text(f"🛑 Halt command sent: {reason}")

    async def cmd_resume(self, update, context) -> None:
        """/resume — resume trading (admin only)."""
        if not self._is_authorized(update):
            await update.message.reply_text("⛔ Not authorized")
            return
        if not self._is_admin(update):
            await update.message.reply_text("⛔ Admin only command")
            return
        msg = SystemAlertMessage(
            source="telegram",
            payload={"severity": "INFO", "message": "Resume trading", "action": "resume"},
        )
        await self.redis.publish("system:alerts", msg)
        await update.message.reply_text("▶️ Resume command sent")

    async def cmd_research(self, update, context) -> None:
        """/research [query] — trigger Perplexity research."""
        if not self._is_authorized(update):
            await update.message.reply_text("⛔ Not authorized")
            return
        if not context.args:
            await update.message.reply_text("Usage: /research <query>")
            return
        query = " ".join(context.args)
        msg = SystemAlertMessage(
            source="telegram",
            payload={"action": "research", "query": query},
        )
        await self.redis.publish("system:alerts", msg)
        await update.message.reply_text(f"🔬 Research requested: {query}")

    async def cmd_reflect(self, update, context) -> None:
        """/reflect — force deep reflection cycle."""
        if not self._is_authorized(update):
            await update.message.reply_text("⛔ Not authorized")
            return
        msg = SystemAlertMessage(
            source="telegram",
            payload={"action": "reflect", "message": "Manual reflection trigger"},
        )
        await self.redis.publish("system:alerts", msg)
        await update.message.reply_text("🔄 Deep reflection requested")

    async def cmd_config(self, update, context) -> None:
        """/config [key] [value] — view/update config (admin for set)."""
        if not self._is_authorized(update):
            await update.message.reply_text("⛔ Not authorized")
            return

        if not context.args:
            text = (
                "⚙️ Config\n"
                f"Alert Cooldown: {self.settings.ALERT_COOLDOWN_SECONDS}s\n"
                f"Silent Hours UTC: {self.settings.SILENT_HOURS_UTC}\n"
                f"Alert on Trade: {self.settings.ALERT_ON_TRADE}\n"
                f"Alert on Reflection: {self.settings.ALERT_ON_REFLECTION}\n"
                f"Alert on Risk Rejection: {self.settings.ALERT_ON_RISK_REJECTION}"
            )
            await update.message.reply_text(text)
            return

        if len(context.args) >= 2:
            if not self._is_admin(update):
                await update.message.reply_text("⛔ Admin only: config set")
                return
            key = context.args[0].lower()
            value = context.args[1]
            if key == "cooldown":
                try:
                    self.settings.ALERT_COOLDOWN_SECONDS = int(value)
                    await update.message.reply_text(f"✅ Cooldown updated to {value}s")
                except ValueError:
                    await update.message.reply_text("❌ Invalid value for cooldown")
            else:
                await update.message.reply_text(f"❌ Unknown config key: {key}")
        else:
            await update.message.reply_text("Usage: /config [key] [value]")
