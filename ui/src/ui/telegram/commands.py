"""All /command handlers."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

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

    async def cmd_status(self, update, context) -> None:
        """/status — equity, PnL, positions, bot state, screener rate."""
        ...

    async def cmd_positions(self, update, context) -> None:
        """/positions — detailed open positions."""
        ...

    async def cmd_halt(self, update, context) -> None:
        """/halt [reason] — emergency halt (admin only)."""
        ...

    async def cmd_resume(self, update, context) -> None:
        """/resume — resume trading (admin only)."""
        ...

    async def cmd_research(self, update, context) -> None:
        """/research [query] — trigger Perplexity research."""
        ...

    async def cmd_reflect(self, update, context) -> None:
        """/reflect — force deep reflection cycle."""
        ...

    async def cmd_playbook(self, update, context) -> None:
        """/playbook — current playbook summary."""
        ...

    async def cmd_trades(self, update, context) -> None:
        """/trades [n=10] — last N closed trades."""
        ...

    async def cmd_performance(self, update, context) -> None:
        """/performance — win rate, Sharpe, PnL, breakdowns."""
        ...

    async def cmd_config(self, update, context) -> None:
        """/config [key] [value] — view/update config (admin for set)."""
        ...
