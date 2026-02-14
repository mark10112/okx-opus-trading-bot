"""Unit tests for db/queries.py — read-only DB query functions."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ui.db.queries import DBQueries


@pytest.fixture
def mock_engine():
    return MagicMock()


@pytest.fixture
def db(mock_engine):
    return DBQueries(engine=mock_engine)


def _make_trade_row(
    *,
    trade_id="t-001",
    symbol="BTC-USDT-SWAP",
    direction="LONG",
    entry_price=100000.0,
    exit_price=101000.0,
    stop_loss=99000.0,
    take_profit=102000.0,
    size=0.01,
    leverage=2.0,
    pnl_usd=10.0,
    pnl_pct=0.01,
    fees_usd=0.5,
    strategy_used="momentum",
    confidence_at_entry=0.75,
    market_regime="trending_up",
    opus_reasoning="Strong trend",
    exit_reason="take_profit",
    status="closed",
    opened_at=None,
    closed_at=None,
    duration_seconds=3600,
):
    now = datetime.now(timezone.utc)
    row = MagicMock()
    row.trade_id = trade_id
    row.symbol = symbol
    row.direction = direction
    row.entry_price = entry_price
    row.exit_price = exit_price
    row.stop_loss = stop_loss
    row.take_profit = take_profit
    row.size = size
    row.leverage = leverage
    row.pnl_usd = pnl_usd
    row.pnl_pct = pnl_pct
    row.fees_usd = fees_usd
    row.strategy_used = strategy_used
    row.confidence_at_entry = confidence_at_entry
    row.market_regime = market_regime
    row.opus_reasoning = opus_reasoning
    row.exit_reason = exit_reason
    row.status = status
    row.opened_at = opened_at or now - timedelta(hours=1)
    row.closed_at = closed_at or now
    row.duration_seconds = duration_seconds
    return row


def _make_playbook_row(
    *,
    version=3,
    playbook_json=None,
    change_summary="Updated regime rules",
    triggered_by="reflection",
):
    row = MagicMock()
    row.version = version
    row.playbook_json = playbook_json or {
        "regime_rules": {"trending_up": {"strategies": ["momentum"]}},
        "lessons": ["Cut losses early"],
    }
    row.change_summary = change_summary
    row.triggered_by = triggered_by
    row.created_at = datetime.now(timezone.utc)
    return row


def _make_perf_snapshot_row(*, equity=100000.0, total_pnl=500.0):
    row = MagicMock()
    row.equity = equity
    row.total_pnl = total_pnl
    row.created_at = datetime.now(timezone.utc)
    return row


def _make_screener_row(*, signal=True, opus_agreed=True):
    row = MagicMock()
    row.signal = signal
    row.opus_agreed = opus_agreed
    row.created_at = datetime.now(timezone.utc)
    return row


# ─── get_equity_and_pnl ───


class TestGetEquityAndPnl:
    async def test_returns_equity_and_pnl(self, db):
        snap = _make_perf_snapshot_row(equity=105000.0, total_pnl=750.0)
        with patch.object(db, "session_factory") as sf:
            session = AsyncMock()
            sf.return_value.__aenter__ = AsyncMock(return_value=session)
            sf.return_value.__aexit__ = AsyncMock(return_value=False)
            result = MagicMock()
            result.scalars.return_value.first.return_value = snap
            session.execute.return_value = result

            equity, pnl = await db.get_equity_and_pnl()

        assert equity == 105000.0
        assert pnl == 750.0

    async def test_returns_zeros_when_no_snapshot(self, db):
        with patch.object(db, "session_factory") as sf:
            session = AsyncMock()
            sf.return_value.__aenter__ = AsyncMock(return_value=session)
            sf.return_value.__aexit__ = AsyncMock(return_value=False)
            result = MagicMock()
            result.scalars.return_value.first.return_value = None
            session.execute.return_value = result

            equity, pnl = await db.get_equity_and_pnl()

        assert equity == 0.0
        assert pnl == 0.0


# ─── get_open_positions ───


class TestGetOpenPositions:
    async def test_returns_open_trades(self, db):
        trade = _make_trade_row(status="open", pnl_usd=None, exit_price=None)
        with patch.object(db, "session_factory") as sf:
            session = AsyncMock()
            sf.return_value.__aenter__ = AsyncMock(return_value=session)
            sf.return_value.__aexit__ = AsyncMock(return_value=False)
            result = MagicMock()
            result.scalars.return_value.all.return_value = [trade]
            session.execute.return_value = result

            positions = await db.get_open_positions()

        assert len(positions) == 1
        assert positions[0]["symbol"] == "BTC-USDT-SWAP"
        assert positions[0]["direction"] == "LONG"
        assert positions[0]["entry_price"] == 100000.0

    async def test_returns_empty_list_when_no_positions(self, db):
        with patch.object(db, "session_factory") as sf:
            session = AsyncMock()
            sf.return_value.__aenter__ = AsyncMock(return_value=session)
            sf.return_value.__aexit__ = AsyncMock(return_value=False)
            result = MagicMock()
            result.scalars.return_value.all.return_value = []
            session.execute.return_value = result

            positions = await db.get_open_positions()

        assert positions == []


# ─── get_recent_trades ───


class TestGetRecentTrades:
    async def test_returns_recent_closed_trades(self, db):
        t1 = _make_trade_row(trade_id="t-001", pnl_usd=50.0)
        t2 = _make_trade_row(trade_id="t-002", pnl_usd=-20.0)
        with patch.object(db, "session_factory") as sf:
            session = AsyncMock()
            sf.return_value.__aenter__ = AsyncMock(return_value=session)
            sf.return_value.__aexit__ = AsyncMock(return_value=False)
            result = MagicMock()
            result.scalars.return_value.all.return_value = [t1, t2]
            session.execute.return_value = result

            trades = await db.get_recent_trades(limit=10)

        assert len(trades) == 2
        assert trades[0]["trade_id"] == "t-001"
        assert trades[1]["pnl_usd"] == -20.0

    async def test_respects_limit(self, db):
        trades_data = [_make_trade_row(trade_id=f"t-{i:03d}") for i in range(5)]
        with patch.object(db, "session_factory") as sf:
            session = AsyncMock()
            sf.return_value.__aenter__ = AsyncMock(return_value=session)
            sf.return_value.__aexit__ = AsyncMock(return_value=False)
            result = MagicMock()
            result.scalars.return_value.all.return_value = trades_data[:3]
            session.execute.return_value = result

            trades = await db.get_recent_trades(limit=3)

        assert len(trades) == 3

    async def test_returns_empty_when_no_trades(self, db):
        with patch.object(db, "session_factory") as sf:
            session = AsyncMock()
            sf.return_value.__aenter__ = AsyncMock(return_value=session)
            sf.return_value.__aexit__ = AsyncMock(return_value=False)
            result = MagicMock()
            result.scalars.return_value.all.return_value = []
            session.execute.return_value = result

            trades = await db.get_recent_trades()

        assert trades == []


# ─── get_latest_playbook ───


class TestGetLatestPlaybook:
    async def test_returns_playbook_dict(self, db):
        pb = _make_playbook_row(version=5)
        with patch.object(db, "session_factory") as sf:
            session = AsyncMock()
            sf.return_value.__aenter__ = AsyncMock(return_value=session)
            sf.return_value.__aexit__ = AsyncMock(return_value=False)
            result = MagicMock()
            result.scalars.return_value.first.return_value = pb
            session.execute.return_value = result

            playbook = await db.get_latest_playbook()

        assert playbook["version"] == 5
        assert "regime_rules" in playbook["playbook_json"]
        assert playbook["triggered_by"] == "reflection"

    async def test_returns_empty_dict_when_no_playbook(self, db):
        with patch.object(db, "session_factory") as sf:
            session = AsyncMock()
            sf.return_value.__aenter__ = AsyncMock(return_value=session)
            sf.return_value.__aexit__ = AsyncMock(return_value=False)
            result = MagicMock()
            result.scalars.return_value.first.return_value = None
            session.execute.return_value = result

            playbook = await db.get_latest_playbook()

        assert playbook == {}


# ─── get_performance_metrics ───


class TestGetPerformanceMetrics:
    async def test_computes_metrics_from_trades(self, db):
        wins = [_make_trade_row(trade_id=f"w-{i}", pnl_usd=100.0) for i in range(7)]
        losses = [_make_trade_row(trade_id=f"l-{i}", pnl_usd=-50.0) for i in range(3)]
        all_trades = wins + losses
        with patch.object(db, "session_factory") as sf:
            session = AsyncMock()
            sf.return_value.__aenter__ = AsyncMock(return_value=session)
            sf.return_value.__aexit__ = AsyncMock(return_value=False)
            result = MagicMock()
            result.scalars.return_value.all.return_value = all_trades
            session.execute.return_value = result

            metrics = await db.get_performance_metrics(trade_count=100)

        assert metrics["total_trades"] == 10
        assert metrics["wins"] == 7
        assert metrics["losses"] == 3
        assert metrics["win_rate"] == pytest.approx(0.7)
        assert metrics["total_pnl"] == pytest.approx(550.0)
        assert metrics["profit_factor"] == pytest.approx(700.0 / 150.0)

    async def test_returns_zero_metrics_when_no_trades(self, db):
        with patch.object(db, "session_factory") as sf:
            session = AsyncMock()
            sf.return_value.__aenter__ = AsyncMock(return_value=session)
            sf.return_value.__aexit__ = AsyncMock(return_value=False)
            result = MagicMock()
            result.scalars.return_value.all.return_value = []
            session.execute.return_value = result

            metrics = await db.get_performance_metrics()

        assert metrics["total_trades"] == 0
        assert metrics["win_rate"] == 0.0
        assert metrics["profit_factor"] == 0.0

    async def test_handles_all_losses(self, db):
        losses = [_make_trade_row(trade_id=f"l-{i}", pnl_usd=-30.0) for i in range(5)]
        with patch.object(db, "session_factory") as sf:
            session = AsyncMock()
            sf.return_value.__aenter__ = AsyncMock(return_value=session)
            sf.return_value.__aexit__ = AsyncMock(return_value=False)
            result = MagicMock()
            result.scalars.return_value.all.return_value = losses
            session.execute.return_value = result

            metrics = await db.get_performance_metrics()

        assert metrics["win_rate"] == 0.0
        assert metrics["profit_factor"] == 0.0
        assert metrics["total_pnl"] == pytest.approx(-150.0)

    async def test_handles_all_wins(self, db):
        wins = [_make_trade_row(trade_id=f"w-{i}", pnl_usd=50.0) for i in range(4)]
        with patch.object(db, "session_factory") as sf:
            session = AsyncMock()
            sf.return_value.__aenter__ = AsyncMock(return_value=session)
            sf.return_value.__aexit__ = AsyncMock(return_value=False)
            result = MagicMock()
            result.scalars.return_value.all.return_value = wins
            session.execute.return_value = result

            metrics = await db.get_performance_metrics()

        assert metrics["win_rate"] == 1.0
        assert metrics["profit_factor"] == float("inf")


# ─── get_screener_pass_rate ───


class TestGetScreenerPassRate:
    async def test_computes_pass_rate(self, db):
        logs = [
            _make_screener_row(signal=True),
            _make_screener_row(signal=True),
            _make_screener_row(signal=False),
            _make_screener_row(signal=False),
            _make_screener_row(signal=True),
        ]
        with patch.object(db, "session_factory") as sf:
            session = AsyncMock()
            sf.return_value.__aenter__ = AsyncMock(return_value=session)
            sf.return_value.__aexit__ = AsyncMock(return_value=False)
            result = MagicMock()
            result.scalars.return_value.all.return_value = logs
            session.execute.return_value = result

            rate = await db.get_screener_pass_rate(hours=24)

        assert rate == pytest.approx(0.6)

    async def test_returns_zero_when_no_logs(self, db):
        with patch.object(db, "session_factory") as sf:
            session = AsyncMock()
            sf.return_value.__aenter__ = AsyncMock(return_value=session)
            sf.return_value.__aexit__ = AsyncMock(return_value=False)
            result = MagicMock()
            result.scalars.return_value.all.return_value = []
            session.execute.return_value = result

            rate = await db.get_screener_pass_rate()

        assert rate == 0.0

    async def test_all_pass(self, db):
        logs = [_make_screener_row(signal=True) for _ in range(10)]
        with patch.object(db, "session_factory") as sf:
            session = AsyncMock()
            sf.return_value.__aenter__ = AsyncMock(return_value=session)
            sf.return_value.__aexit__ = AsyncMock(return_value=False)
            result = MagicMock()
            result.scalars.return_value.all.return_value = logs
            session.execute.return_value = result

            rate = await db.get_screener_pass_rate()

        assert rate == pytest.approx(1.0)


# ─── get_latest_decision ───


class TestGetLatestDecision:
    async def test_returns_decision_dict(self, db):
        trade = _make_trade_row(
            trade_id="t-latest",
            strategy_used="breakout",
            confidence_at_entry=0.85,
            opus_reasoning="Breakout confirmed",
        )
        with patch.object(db, "session_factory") as sf:
            session = AsyncMock()
            sf.return_value.__aenter__ = AsyncMock(return_value=session)
            sf.return_value.__aexit__ = AsyncMock(return_value=False)
            result = MagicMock()
            result.scalars.return_value.first.return_value = trade
            session.execute.return_value = result

            decision = await db.get_latest_decision()

        assert decision is not None
        assert decision["trade_id"] == "t-latest"
        assert decision["strategy"] == "breakout"
        assert decision["confidence"] == 0.85
        assert decision["reasoning"] == "Breakout confirmed"

    async def test_returns_none_when_no_decision(self, db):
        with patch.object(db, "session_factory") as sf:
            session = AsyncMock()
            sf.return_value.__aenter__ = AsyncMock(return_value=session)
            sf.return_value.__aexit__ = AsyncMock(return_value=False)
            result = MagicMock()
            result.scalars.return_value.first.return_value = None
            session.execute.return_value = result

            decision = await db.get_latest_decision()

        assert decision is None


# ─── get_daily_trade_summary ───


class TestGetDailyTradeSummary:
    async def test_computes_daily_summary(self, db):
        now = datetime.now(timezone.utc)
        trades = [
            _make_trade_row(trade_id="d-1", pnl_usd=100.0, opened_at=now - timedelta(hours=2)),
            _make_trade_row(trade_id="d-2", pnl_usd=-30.0, opened_at=now - timedelta(hours=1)),
            _make_trade_row(trade_id="d-3", pnl_usd=50.0, opened_at=now - timedelta(minutes=30)),
        ]
        with patch.object(db, "session_factory") as sf:
            session = AsyncMock()
            sf.return_value.__aenter__ = AsyncMock(return_value=session)
            sf.return_value.__aexit__ = AsyncMock(return_value=False)
            result = MagicMock()
            result.scalars.return_value.all.return_value = trades
            session.execute.return_value = result

            summary = await db.get_daily_trade_summary()

        assert summary["trade_count"] == 3
        assert summary["wins"] == 2
        assert summary["losses"] == 1
        assert summary["total_pnl"] == pytest.approx(120.0)

    async def test_returns_zero_summary_when_no_trades(self, db):
        with patch.object(db, "session_factory") as sf:
            session = AsyncMock()
            sf.return_value.__aenter__ = AsyncMock(return_value=session)
            sf.return_value.__aexit__ = AsyncMock(return_value=False)
            result = MagicMock()
            result.scalars.return_value.all.return_value = []
            session.execute.return_value = result

            summary = await db.get_daily_trade_summary()

        assert summary["trade_count"] == 0
        assert summary["wins"] == 0
        assert summary["losses"] == 0
        assert summary["total_pnl"] == 0.0
