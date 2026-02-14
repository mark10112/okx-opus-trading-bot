"""Unit tests for DB repositories — mock AsyncSession."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
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
from orchestrator.db.repository import (
    PerformanceSnapshotRepository,
    PlaybookRepository,
    ReflectionRepository,
    ResearchCacheRepository,
    RiskRejectionRepository,
    ScreenerLogRepository,
    TradeRepository,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_session():
    """Create a mock AsyncSession with context manager support."""
    session = AsyncMock(spec=AsyncSession)
    session.commit = AsyncMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.execute = AsyncMock()
    session.add = MagicMock()
    return session


@pytest.fixture
def session_factory(mock_session):
    """Create a mock async_sessionmaker that yields mock_session.

    async_sessionmaker.__call__() returns a context manager (not a coroutine),
    so we use MagicMock for the factory and wire up async context manager protocol.
    """
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=mock_session)
    ctx.__aexit__ = AsyncMock(return_value=False)

    factory = MagicMock()
    factory.return_value = ctx
    return factory


# ---------------------------------------------------------------------------
# TradeRepository
# ---------------------------------------------------------------------------


class TestTradeRepository:
    @pytest.fixture
    def repo(self, session_factory):
        return TradeRepository(session_factory)

    async def test_create_returns_trade_id(self, repo, mock_session):
        """create() should add a TradeORM, flush, and return the trade_id."""
        trade_data = {
            "trade_id": "t-123",
            "opened_at": datetime.now(timezone.utc),
            "symbol": "BTC-USDT-SWAP",
            "direction": "LONG",
            "entry_price": Decimal("60000.00"),
            "stop_loss": Decimal("58000.00"),
            "take_profit": Decimal("65000.00"),
            "size": Decimal("0.01"),
            "size_pct": 0.02,
            "leverage": 2.0,
            "strategy_used": "trend_follow",
            "confidence_at_entry": 0.75,
            "market_regime": "trending_up",
            "opus_reasoning": "Strong uptrend",
            "status": "open",
        }
        result = await repo.create(trade_data)
        assert result == "t-123"
        mock_session.add.assert_called_once()
        mock_session.flush.assert_awaited_once()

    async def test_update_modifies_fields(self, repo, mock_session):
        """update() should find trade by trade_id and update fields."""
        mock_result = MagicMock()
        mock_trade = MagicMock(spec=TradeORM)
        mock_result.scalar_one_or_none.return_value = mock_trade
        mock_session.execute.return_value = mock_result

        await repo.update("t-123", {"status": "closed", "pnl_usd": 150.0})
        mock_session.execute.assert_awaited_once()
        mock_session.flush.assert_awaited_once()

    async def test_update_nonexistent_raises(self, repo, mock_session):
        """update() should raise ValueError if trade not found."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        with pytest.raises(ValueError, match="Trade not found"):
            await repo.update("nonexistent", {"status": "closed"})

    async def test_get_open_returns_list(self, repo, mock_session):
        """get_open() should return list of TradeRecord for open trades."""
        mock_trade = MagicMock(spec=TradeORM)
        mock_trade.trade_id = "t-1"
        mock_trade.opened_at = datetime.now(timezone.utc)
        mock_trade.closed_at = None
        mock_trade.duration_seconds = None
        mock_trade.symbol = "BTC-USDT-SWAP"
        mock_trade.direction = "LONG"
        mock_trade.entry_price = Decimal("60000")
        mock_trade.exit_price = None
        mock_trade.stop_loss = Decimal("58000")
        mock_trade.take_profit = Decimal("65000")
        mock_trade.size = Decimal("0.01")
        mock_trade.size_pct = 0.02
        mock_trade.leverage = 2.0
        mock_trade.pnl_usd = None
        mock_trade.pnl_pct = None
        mock_trade.fees_usd = None
        mock_trade.strategy_used = "trend_follow"
        mock_trade.confidence_at_entry = 0.75
        mock_trade.market_regime = "trending_up"
        mock_trade.opus_reasoning = "test"
        mock_trade.indicators_entry = None
        mock_trade.indicators_exit = None
        mock_trade.research_context = None
        mock_trade.self_review = None
        mock_trade.exit_reason = None
        mock_trade.status = "open"
        mock_trade.okx_order_id = None
        mock_trade.okx_algo_id = None

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_trade]
        mock_session.execute.return_value = mock_result

        trades = await repo.get_open()
        assert len(trades) == 1
        assert trades[0].trade_id == "t-1"
        assert trades[0].status == "open"

    async def test_get_open_empty(self, repo, mock_session):
        """get_open() should return empty list when no open trades."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        trades = await repo.get_open()
        assert trades == []

    async def test_get_recent_closed_default_limit(self, repo, mock_session):
        """get_recent_closed() should use default limit=20."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        trades = await repo.get_recent_closed()
        assert trades == []
        mock_session.execute.assert_awaited_once()

    async def test_get_recent_closed_custom_limit(self, repo, mock_session):
        """get_recent_closed() should respect custom limit."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        await repo.get_recent_closed(limit=5)
        mock_session.execute.assert_awaited_once()

    async def test_get_trades_since(self, repo, mock_session):
        """get_trades_since() should filter by opened_at >= since."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        since = datetime.now(timezone.utc) - timedelta(hours=6)
        trades = await repo.get_trades_since(since)
        assert trades == []
        mock_session.execute.assert_awaited_once()


# ---------------------------------------------------------------------------
# PlaybookRepository
# ---------------------------------------------------------------------------


class TestPlaybookRepository:
    @pytest.fixture
    def repo(self, session_factory):
        return PlaybookRepository(session_factory)

    async def test_get_latest_returns_none_when_empty(self, repo, mock_session):
        """get_latest() should return None when no playbook versions exist."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await repo.get_latest()
        assert result is None

    async def test_get_latest_returns_dict(self, repo, mock_session):
        """get_latest() should return playbook dict when version exists."""
        mock_pb = MagicMock(spec=PlaybookVersionORM)
        mock_pb.version = 1
        mock_pb.playbook_json = {"version": 1, "market_regime_rules": {}}
        mock_pb.change_summary = "Initial"
        mock_pb.triggered_by = "init"
        mock_pb.performance_at_update = None
        mock_pb.created_at = datetime.now(timezone.utc)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_pb
        mock_session.execute.return_value = mock_result

        result = await repo.get_latest()
        assert result is not None
        assert result["version"] == 1
        assert result["playbook_json"] == {"version": 1, "market_regime_rules": {}}

    async def test_save_version_returns_version_number(self, repo, mock_session):
        """save_version() should add ORM, flush, and return version."""
        data = {
            "version": 2,
            "playbook_json": {"version": 2},
            "change_summary": "Updated strategies",
            "triggered_by": "reflection",
            "performance_at_update": {"win_rate": 0.6},
        }
        mock_session.refresh = AsyncMock(
            side_effect=lambda obj: setattr(obj, "version", 2)
        )

        result = await repo.save_version(data)
        assert result == 2
        mock_session.add.assert_called_once()
        mock_session.flush.assert_awaited_once()

    async def test_get_history_returns_ordered_list(self, repo, mock_session):
        """get_history() should return list ordered by version desc."""
        mock_pb1 = MagicMock(spec=PlaybookVersionORM)
        mock_pb1.version = 2
        mock_pb1.playbook_json = {"version": 2}
        mock_pb1.change_summary = "v2"
        mock_pb1.triggered_by = "reflection"
        mock_pb1.performance_at_update = None
        mock_pb1.created_at = datetime.now(timezone.utc)

        mock_pb2 = MagicMock(spec=PlaybookVersionORM)
        mock_pb2.version = 1
        mock_pb2.playbook_json = {"version": 1}
        mock_pb2.change_summary = "v1"
        mock_pb2.triggered_by = "init"
        mock_pb2.performance_at_update = None
        mock_pb2.created_at = datetime.now(timezone.utc) - timedelta(hours=1)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_pb1, mock_pb2]
        mock_session.execute.return_value = mock_result

        history = await repo.get_history()
        assert len(history) == 2
        assert history[0]["version"] == 2
        assert history[1]["version"] == 1

    async def test_get_history_empty(self, repo, mock_session):
        """get_history() should return empty list when no versions."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        history = await repo.get_history()
        assert history == []


# ---------------------------------------------------------------------------
# ReflectionRepository
# ---------------------------------------------------------------------------


class TestReflectionRepository:
    @pytest.fixture
    def repo(self, session_factory):
        return ReflectionRepository(session_factory)

    async def test_save_returns_id(self, repo, mock_session):
        """save() should add ReflectionLogORM and return id."""
        data = {
            "reflection_type": "post_trade",
            "trade_ids": [1, 2],
            "input_prompt": "Review these trades",
            "output_json": {"lesson": "Be patient"},
            "playbook_changes": None,
            "old_version": 1,
            "new_version": None,
        }
        mock_session.refresh = AsyncMock(
            side_effect=lambda obj: setattr(obj, "id", 42)
        )

        result = await repo.save(data)
        assert result == 42
        mock_session.add.assert_called_once()
        mock_session.flush.assert_awaited_once()

    async def test_get_last_time_returns_datetime(self, repo, mock_session):
        """get_last_time() should return created_at of most recent reflection."""
        now = datetime.now(timezone.utc)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = now
        mock_session.execute.return_value = mock_result

        result = await repo.get_last_time()
        assert result == now

    async def test_get_last_time_returns_none_when_empty(self, repo, mock_session):
        """get_last_time() should return None when no reflections exist."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await repo.get_last_time()
        assert result is None

    async def test_get_trades_since_last(self, repo, mock_session):
        """get_trades_since_last() should return trades since last reflection."""
        # First call: get_last_time returns a datetime
        now = datetime.now(timezone.utc)
        mock_result1 = MagicMock()
        mock_result1.scalar_one_or_none.return_value = now - timedelta(hours=2)

        # Second call: get trades
        mock_trade = MagicMock(spec=TradeORM)
        mock_trade.trade_id = "t-1"
        mock_trade.opened_at = now - timedelta(hours=1)
        mock_trade.closed_at = now
        mock_trade.duration_seconds = 3600
        mock_trade.symbol = "BTC-USDT-SWAP"
        mock_trade.direction = "LONG"
        mock_trade.entry_price = Decimal("60000")
        mock_trade.exit_price = Decimal("61000")
        mock_trade.stop_loss = Decimal("58000")
        mock_trade.take_profit = Decimal("65000")
        mock_trade.size = Decimal("0.01")
        mock_trade.size_pct = 0.02
        mock_trade.leverage = 2.0
        mock_trade.pnl_usd = 100.0
        mock_trade.pnl_pct = 0.0167
        mock_trade.fees_usd = 1.0
        mock_trade.strategy_used = "trend_follow"
        mock_trade.confidence_at_entry = 0.75
        mock_trade.market_regime = "trending_up"
        mock_trade.opus_reasoning = "test"
        mock_trade.indicators_entry = None
        mock_trade.indicators_exit = None
        mock_trade.research_context = None
        mock_trade.self_review = None
        mock_trade.exit_reason = "tp_hit"
        mock_trade.status = "closed"
        mock_trade.okx_order_id = None
        mock_trade.okx_algo_id = None

        mock_result2 = MagicMock()
        mock_result2.scalars.return_value.all.return_value = [mock_trade]

        mock_session.execute.side_effect = [mock_result1, mock_result2]

        trades = await repo.get_trades_since_last()
        assert len(trades) == 1
        assert trades[0].trade_id == "t-1"

    async def test_get_trades_since_last_no_reflection(self, repo, mock_session):
        """get_trades_since_last() returns all closed trades when no reflection exists."""
        mock_result1 = MagicMock()
        mock_result1.scalar_one_or_none.return_value = None

        mock_result2 = MagicMock()
        mock_result2.scalars.return_value.all.return_value = []

        mock_session.execute.side_effect = [mock_result1, mock_result2]

        trades = await repo.get_trades_since_last()
        assert trades == []


# ---------------------------------------------------------------------------
# ScreenerLogRepository
# ---------------------------------------------------------------------------


class TestScreenerLogRepository:
    @pytest.fixture
    def repo(self, session_factory):
        return ScreenerLogRepository(session_factory)

    async def test_log_returns_id(self, repo, mock_session):
        """log() should add ScreenerLogORM and return id."""
        data = {
            "symbol": "BTC-USDT-SWAP",
            "signal": True,
            "reason": "RSI oversold",
            "snapshot_json": {"rsi": 25},
            "tokens_used": 50,
            "latency_ms": 200,
        }
        mock_session.refresh = AsyncMock(
            side_effect=lambda obj: setattr(obj, "id", 10)
        )

        result = await repo.log(data)
        assert result == 10
        mock_session.add.assert_called_once()
        mock_session.flush.assert_awaited_once()

    async def test_update_opus_agreement(self, repo, mock_session):
        """update_opus_agreement() should update opus_action and opus_agreed."""
        mock_log = MagicMock(spec=ScreenerLogORM)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_log
        mock_session.execute.return_value = mock_result

        await repo.update_opus_agreement(10, "OPEN_LONG", True)
        assert mock_log.opus_action == "OPEN_LONG"
        assert mock_log.opus_agreed is True
        mock_session.flush.assert_awaited_once()

    async def test_update_opus_agreement_nonexistent(self, repo, mock_session):
        """update_opus_agreement() should raise ValueError if log not found."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        with pytest.raises(ValueError, match="Screener log not found"):
            await repo.update_opus_agreement(999, "HOLD", False)


# ---------------------------------------------------------------------------
# ResearchCacheRepository
# ---------------------------------------------------------------------------


class TestResearchCacheRepository:
    @pytest.fixture
    def repo(self, session_factory):
        return ResearchCacheRepository(session_factory)

    async def test_get_cached_returns_response_when_fresh(self, repo, mock_session):
        """get_cached() should return response_json when within TTL."""
        now = datetime.now(timezone.utc)
        mock_cache = MagicMock(spec=ResearchCacheORM)
        mock_cache.response_json = {"summary": "BTC bullish"}
        mock_cache.created_at = now - timedelta(minutes=30)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_cache
        mock_session.execute.return_value = mock_result

        result = await repo.get_cached("BTC outlook", ttl_seconds=3600)
        assert result == {"summary": "BTC bullish"}

    async def test_get_cached_returns_none_when_expired(self, repo, mock_session):
        """get_cached() should return None when cache is expired."""
        now = datetime.now(timezone.utc)
        mock_cache = MagicMock(spec=ResearchCacheORM)
        mock_cache.response_json = {"summary": "old data"}
        mock_cache.created_at = now - timedelta(hours=2)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_cache
        mock_session.execute.return_value = mock_result

        result = await repo.get_cached("BTC outlook", ttl_seconds=3600)
        assert result is None

    async def test_get_cached_returns_none_when_not_found(self, repo, mock_session):
        """get_cached() should return None when no cache entry exists."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await repo.get_cached("unknown query")
        assert result is None

    async def test_save_returns_id(self, repo, mock_session):
        """save() should add ResearchCacheORM and return id."""
        mock_session.refresh = AsyncMock(
            side_effect=lambda obj: setattr(obj, "id", 5)
        )

        result = await repo.save("BTC outlook", {"summary": "bullish"})
        assert result == 5
        mock_session.add.assert_called_once()
        mock_session.flush.assert_awaited_once()


# ---------------------------------------------------------------------------
# RiskRejectionRepository
# ---------------------------------------------------------------------------


class TestRiskRejectionRepository:
    @pytest.fixture
    def repo(self, session_factory):
        return RiskRejectionRepository(session_factory)

    async def test_log_returns_id(self, repo, mock_session):
        """log() should add RiskRejectionORM and return id."""
        mock_session.refresh = AsyncMock(
            side_effect=lambda obj: setattr(obj, "id", 7)
        )

        result = await repo.log(
            decision={"action": "OPEN_LONG", "size_pct": 0.10},
            failed_rules=["max_single_trade"],
            account_state={"equity": 10000},
        )
        assert result == 7
        mock_session.add.assert_called_once()
        mock_session.flush.assert_awaited_once()


# ---------------------------------------------------------------------------
# PerformanceSnapshotRepository
# ---------------------------------------------------------------------------


class TestPerformanceSnapshotRepository:
    @pytest.fixture
    def repo(self, session_factory):
        return PerformanceSnapshotRepository(session_factory)

    async def test_save_returns_id(self, repo, mock_session):
        """save() should add PerformanceSnapshotORM and return id."""
        mock_session.refresh = AsyncMock(
            side_effect=lambda obj: setattr(obj, "id", 3)
        )

        data = {
            "equity": 10500.0,
            "total_pnl": 500.0,
            "win_rate": 0.65,
            "profit_factor": 2.1,
            "sharpe_ratio": 1.5,
            "max_drawdown": 0.03,
            "total_trades": 20,
            "metrics_json": {"avg_rr": 2.0},
        }
        result = await repo.save("daily", data)
        assert result == 3
        mock_session.add.assert_called_once()
        mock_session.flush.assert_awaited_once()

    async def test_save_hourly(self, repo, mock_session):
        """save() should accept 'hourly' snapshot_type."""
        mock_session.refresh = AsyncMock(
            side_effect=lambda obj: setattr(obj, "id", 4)
        )

        result = await repo.save("hourly", {"equity": 10000.0})
        assert result == 4

    async def test_save_weekly(self, repo, mock_session):
        """save() should accept 'weekly' snapshot_type."""
        mock_session.refresh = AsyncMock(
            side_effect=lambda obj: setattr(obj, "id", 5)
        )

        result = await repo.save("weekly", {"equity": 11000.0})
        assert result == 5
