"""DB repositories: TradeRepo, PlaybookRepo, ReflectionRepo, etc."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from orchestrator.db.models import (
    PerformanceSnapshotORM,
    PlaybookVersionORM,
    ReflectionLogORM,
    ResearchCacheORM,
    RiskRejectionORM,
    ScreenerLogORM,
    TradeORM,
)
from orchestrator.models.trade import TradeRecord

logger = structlog.get_logger()


def _orm_to_trade_record(orm: TradeORM) -> TradeRecord:
    """Convert TradeORM to TradeRecord Pydantic model."""
    return TradeRecord(
        trade_id=orm.trade_id,
        opened_at=orm.opened_at,
        closed_at=orm.closed_at,
        duration_seconds=orm.duration_seconds,
        symbol=orm.symbol,
        direction=orm.direction,
        entry_price=orm.entry_price,
        exit_price=orm.exit_price,
        stop_loss=orm.stop_loss,
        take_profit=orm.take_profit,
        size=orm.size,
        size_pct=orm.size_pct,
        leverage=orm.leverage or 1.0,
        pnl_usd=orm.pnl_usd,
        pnl_pct=orm.pnl_pct,
        fees_usd=orm.fees_usd,
        strategy_used=orm.strategy_used or "",
        confidence_at_entry=orm.confidence_at_entry or 0.0,
        market_regime=orm.market_regime or "",
        opus_reasoning=orm.opus_reasoning or "",
        indicators_entry=orm.indicators_entry,
        indicators_exit=orm.indicators_exit,
        research_context=orm.research_context,
        self_review=orm.self_review,
        exit_reason=orm.exit_reason,
        status=orm.status,
        okx_order_id=orm.okx_order_id,
        okx_algo_id=orm.okx_algo_id,
    )


class TradeRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def create(self, trade: dict) -> str:
        """Create a new trade record. Returns trade_id."""
        async with self.session_factory() as session:
            orm = TradeORM(**trade)
            session.add(orm)
            await session.flush()
            trade_id = orm.trade_id
            await session.commit()
            logger.info("trade_created", trade_id=trade_id)
            return trade_id

    async def update(self, trade_id: str, data: dict) -> None:
        """Update trade fields by trade_id."""
        async with self.session_factory() as session:
            stmt = select(TradeORM).where(TradeORM.trade_id == trade_id)
            result = await session.execute(stmt)
            trade = result.scalar_one_or_none()
            if trade is None:
                raise ValueError(f"Trade not found: {trade_id}")
            for key, value in data.items():
                setattr(trade, key, value)
            await session.flush()
            await session.commit()
            logger.info("trade_updated", trade_id=trade_id, fields=list(data.keys()))

    async def get_open(self) -> list[TradeRecord]:
        """Get all open trades."""
        async with self.session_factory() as session:
            stmt = select(TradeORM).where(TradeORM.status == "open")
            result = await session.execute(stmt)
            return [_orm_to_trade_record(t) for t in result.scalars().all()]

    async def get_recent_closed(self, limit: int = 20) -> list[TradeRecord]:
        """Get recently closed trades, ordered by closed_at desc."""
        async with self.session_factory() as session:
            stmt = (
                select(TradeORM)
                .where(TradeORM.status == "closed")
                .order_by(TradeORM.closed_at.desc())
                .limit(limit)
            )
            result = await session.execute(stmt)
            return [_orm_to_trade_record(t) for t in result.scalars().all()]

    async def get_trades_since(self, since: datetime) -> list[TradeRecord]:
        """Get all trades opened since a given datetime."""
        async with self.session_factory() as session:
            stmt = (
                select(TradeORM)
                .where(TradeORM.opened_at >= since)
                .order_by(TradeORM.opened_at.desc())
            )
            result = await session.execute(stmt)
            return [_orm_to_trade_record(t) for t in result.scalars().all()]


class PlaybookRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def get_latest(self) -> dict | None:
        """Get the latest playbook version. Returns None if no versions exist."""
        async with self.session_factory() as session:
            stmt = (
                select(PlaybookVersionORM)
                .order_by(PlaybookVersionORM.version.desc())
                .limit(1)
            )
            result = await session.execute(stmt)
            pb = result.scalar_one_or_none()
            if pb is None:
                return None
            return {
                "version": pb.version,
                "playbook_json": pb.playbook_json,
                "change_summary": pb.change_summary,
                "triggered_by": pb.triggered_by,
                "performance_at_update": pb.performance_at_update,
                "created_at": pb.created_at,
            }

    async def save_version(self, data: dict) -> int:
        """Save a new playbook version. Returns version number."""
        async with self.session_factory() as session:
            orm = PlaybookVersionORM(**data)
            session.add(orm)
            await session.flush()
            await session.refresh(orm)
            version = orm.version
            await session.commit()
            logger.info("playbook_saved", version=version)
            return version

    async def get_history(self, limit: int = 20) -> list[dict]:
        """Get playbook version history, ordered by version desc."""
        async with self.session_factory() as session:
            stmt = (
                select(PlaybookVersionORM)
                .order_by(PlaybookVersionORM.version.desc())
                .limit(limit)
            )
            result = await session.execute(stmt)
            return [
                {
                    "version": pb.version,
                    "playbook_json": pb.playbook_json,
                    "change_summary": pb.change_summary,
                    "triggered_by": pb.triggered_by,
                    "performance_at_update": pb.performance_at_update,
                    "created_at": pb.created_at,
                }
                for pb in result.scalars().all()
            ]


class ReflectionRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def save(self, data: dict) -> int:
        """Save a reflection log. Returns id."""
        async with self.session_factory() as session:
            orm = ReflectionLogORM(**data)
            session.add(orm)
            await session.flush()
            await session.refresh(orm)
            log_id = orm.id
            await session.commit()
            logger.info("reflection_saved", id=log_id, type=data.get("reflection_type"))
            return log_id

    async def get_last_time(self) -> datetime | None:
        """Get created_at of the most recent reflection. Returns None if none exist."""
        async with self.session_factory() as session:
            stmt = (
                select(ReflectionLogORM.created_at)
                .order_by(ReflectionLogORM.created_at.desc())
                .limit(1)
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def get_trades_since_last(self) -> list[TradeRecord]:
        """Get closed trades since the last reflection."""
        async with self.session_factory() as session:
            # Get last reflection time
            stmt_last = (
                select(ReflectionLogORM.created_at)
                .order_by(ReflectionLogORM.created_at.desc())
                .limit(1)
            )
            result_last = await session.execute(stmt_last)
            last_time = result_last.scalar_one_or_none()

            # Get trades since that time (or all closed trades if no reflection)
            stmt_trades = select(TradeORM).where(TradeORM.status == "closed")
            if last_time is not None:
                stmt_trades = stmt_trades.where(TradeORM.closed_at >= last_time)
            stmt_trades = stmt_trades.order_by(TradeORM.closed_at.desc())

            result_trades = await session.execute(stmt_trades)
            return [_orm_to_trade_record(t) for t in result_trades.scalars().all()]


class ScreenerLogRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def log(self, data: dict) -> int:
        """Log a screener result. Returns id."""
        async with self.session_factory() as session:
            orm = ScreenerLogORM(**data)
            session.add(orm)
            await session.flush()
            await session.refresh(orm)
            log_id = orm.id
            await session.commit()
            logger.info("screener_logged", id=log_id, signal=data.get("signal"))
            return log_id

    async def update_opus_agreement(
        self, log_id: int, opus_action: str, agreed: bool
    ) -> None:
        """Update a screener log with Opus agreement info."""
        async with self.session_factory() as session:
            stmt = select(ScreenerLogORM).where(ScreenerLogORM.id == log_id)
            result = await session.execute(stmt)
            log_entry = result.scalar_one_or_none()
            if log_entry is None:
                raise ValueError(f"Screener log not found: {log_id}")
            log_entry.opus_action = opus_action
            log_entry.opus_agreed = agreed
            await session.flush()
            await session.commit()
            logger.info(
                "screener_opus_updated", id=log_id, action=opus_action, agreed=agreed
            )


class ResearchCacheRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def get_cached(self, query: str, ttl_seconds: int = 3600) -> dict | None:
        """Get cached research response if within TTL. Returns None if expired or missing."""
        async with self.session_factory() as session:
            stmt = (
                select(ResearchCacheORM)
                .where(ResearchCacheORM.query == query)
                .order_by(ResearchCacheORM.created_at.desc())
                .limit(1)
            )
            result = await session.execute(stmt)
            cache = result.scalar_one_or_none()
            if cache is None:
                return None
            # Check TTL
            now = datetime.now(timezone.utc)
            created = cache.created_at
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            if (now - created).total_seconds() > ttl_seconds:
                return None
            return cache.response_json

    async def save(self, query: str, response: dict) -> int:
        """Save a research cache entry. Returns id."""
        async with self.session_factory() as session:
            orm = ResearchCacheORM(query=query, response_json=response)
            session.add(orm)
            await session.flush()
            await session.refresh(orm)
            cache_id = orm.id
            await session.commit()
            logger.info("research_cached", id=cache_id, query=query[:50])
            return cache_id


class RiskRejectionRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def log(
        self, decision: dict, failed_rules: list, account_state: dict
    ) -> int:
        """Log a risk rejection. Returns id."""
        async with self.session_factory() as session:
            orm = RiskRejectionORM(
                decision_json=decision,
                failed_rules=failed_rules,
                account_state=account_state,
            )
            session.add(orm)
            await session.flush()
            await session.refresh(orm)
            log_id = orm.id
            await session.commit()
            logger.info("risk_rejection_logged", id=log_id, rules=failed_rules)
            return log_id


class PerformanceSnapshotRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def save(self, snapshot_type: str, data: dict) -> int:
        """Save a performance snapshot. Returns id."""
        async with self.session_factory() as session:
            orm = PerformanceSnapshotORM(snapshot_type=snapshot_type, **data)
            session.add(orm)
            await session.flush()
            await session.refresh(orm)
            snap_id = orm.id
            await session.commit()
            logger.info("performance_snapshot_saved", id=snap_id, type=snapshot_type)
            return snap_id
