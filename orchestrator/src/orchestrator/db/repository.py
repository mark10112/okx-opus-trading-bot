"""DB repositories: TradeRepo, PlaybookRepo, ReflectionRepo, etc."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

if TYPE_CHECKING:
    pass

logger = structlog.get_logger()


class TradeRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def create(self, trade: dict) -> int:
        ...

    async def update(self, trade_id: str, data: dict) -> None:
        ...

    async def get_open(self) -> list[dict]:
        ...

    async def get_recent_closed(self, limit: int = 20) -> list[dict]:
        ...

    async def get_trades_since(self, since: object) -> list[dict]:
        ...


class PlaybookRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def get_latest(self) -> dict | None:
        ...

    async def save_version(self, data: dict) -> int:
        ...

    async def get_history(self, limit: int = 20) -> list[dict]:
        ...


class ReflectionRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def save(self, data: dict) -> int:
        ...

    async def get_last_time(self) -> object | None:
        ...

    async def get_trades_since_last(self) -> list[dict]:
        ...


class ScreenerLogRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def log(self, data: dict) -> int:
        ...

    async def update_opus_agreement(self, log_id: int, opus_action: str, agreed: bool) -> None:
        ...


class ResearchCacheRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def get_cached(self, query: str, ttl_seconds: int = 3600) -> dict | None:
        ...

    async def save(self, query: str, response: dict) -> int:
        ...


class RiskRejectionRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def log(self, decision: dict, failed_rules: list, account_state: dict) -> int:
        ...


class PerformanceSnapshotRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def save(self, snapshot_type: str, data: dict) -> int:
        ...
