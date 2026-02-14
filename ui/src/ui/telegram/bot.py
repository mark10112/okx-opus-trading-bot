"""Application builder + handlers setup."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

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

    async def start(self) -> None:
        """
        1. Build Application with bot token
        2. Register command handlers
        3. Start alert listener (Redis subscriber)
        4. Start polling for Telegram updates
        """
        ...

    async def stop(self) -> None:
        """Gracefully stop bot + alert listener."""
        ...

    def _setup_handlers(self) -> None:
        """Register all command handlers."""
        ...

    def _check_authorized(self, update) -> bool:
        """Check if message comes from authorized chat_id."""
        ...
