"""Unit tests for ReflectionEngine — post-trade + periodic deep reflection."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from orchestrator.models.playbook import Playbook, RegimeRule, StrategyDef
from orchestrator.models.reflection import DeepReflectionResult, TradeReview
from orchestrator.reflection_engine import ReflectionEngine


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_opus():
    opus = AsyncMock()
    opus.reflect_trade = AsyncMock(return_value=TradeReview(
        outcome="win",
        execution_quality="good",
        entry_timing="good",
        exit_timing="early",
        what_went_right=["Good entry"],
        what_went_wrong=["Exited early"],
        lesson="Hold winners longer",
        should_update_playbook=False,
    ))
    opus.deep_reflect = AsyncMock(return_value=DeepReflectionResult(
        updated_playbook=Playbook(
            version=2,
            market_regime_rules={
                "trending_up": RegimeRule(
                    preferred_strategies=["momentum"],
                    max_position_pct=0.05,
                ),
            },
            strategy_definitions={
                "momentum": StrategyDef(
                    entry="EMA20 > EMA50",
                    exit="RSI > 80",
                    historical_winrate=0.67,
                ),
            },
        ),
        pattern_insights=["Momentum works best in trends"],
        bias_findings=["Exit winners too early"],
        discipline_score=80,
        summary="Good overall performance",
    ))
    return opus


@pytest.fixture
def mock_playbook_mgr():
    mgr = AsyncMock()
    mgr.get_latest = AsyncMock(return_value=Playbook(version=1))
    mgr.save_version = AsyncMock(return_value=2)
    return mgr


@pytest.fixture
def mock_prompt_builder():
    builder = MagicMock()
    builder.build_post_trade_prompt.return_value = "post-trade prompt"
    builder.build_deep_reflection_prompt.return_value = "deep reflection prompt"
    return builder


@pytest.fixture
def mock_trade_repo():
    repo = AsyncMock()
    repo.update = AsyncMock()
    repo.get_recent_closed = AsyncMock(return_value=[])
    return repo


@pytest.fixture
def mock_reflection_repo():
    repo = AsyncMock()
    repo.save = AsyncMock(return_value=1)
    repo.get_trades_since_last = AsyncMock(return_value=[])
    return repo


@pytest.fixture
def mock_redis():
    redis = AsyncMock()
    redis.publish = AsyncMock()
    return redis


@pytest.fixture
def engine(mock_opus, mock_playbook_mgr, mock_prompt_builder, mock_trade_repo, mock_reflection_repo, mock_redis):
    return ReflectionEngine(
        opus=mock_opus,
        playbook_mgr=mock_playbook_mgr,
        prompt_builder=mock_prompt_builder,
        trade_repo=mock_trade_repo,
        reflection_repo=mock_reflection_repo,
        redis=mock_redis,
    )


@pytest.fixture
def sample_trade():
    return {
        "trade_id": "t-1",
        "symbol": "BTC-USDT-SWAP",
        "direction": "LONG",
        "entry_price": 59000.0,
        "exit_price": 60500.0,
        "stop_loss": 58000.0,
        "take_profit": 62000.0,
        "pnl_usd": 150.0,
        "pnl_pct": 0.025,
        "strategy_used": "momentum",
        "confidence_at_entry": 0.80,
        "market_regime": "trending_up",
        "leverage": 2.0,
        "indicators_entry": {"rsi": 55.0, "adx": 30.0},
        "indicators_exit": {"rsi": 72.0, "adx": 28.0},
    }


def _make_trade(pnl_usd, strategy="momentum", regime="trending_up", confidence=0.7):
    """Helper to create trade dicts for testing."""
    return {
        "trade_id": f"t-{abs(hash(str(pnl_usd))) % 1000}",
        "symbol": "BTC-USDT-SWAP",
        "direction": "LONG" if pnl_usd > 0 else "SHORT",
        "pnl_usd": pnl_usd,
        "pnl_pct": pnl_usd / 10000.0,
        "strategy_used": strategy,
        "market_regime": regime,
        "confidence_at_entry": confidence,
        "entry_price": 60000.0,
        "exit_price": 60000.0 + pnl_usd,
        "leverage": 2.0,
    }


# ---------------------------------------------------------------------------
# post_trade_reflection()
# ---------------------------------------------------------------------------


class TestPostTradeReflection:
    async def test_returns_review_dict(self, engine, sample_trade):
        result = await engine.post_trade_reflection(sample_trade)
        assert isinstance(result, dict)
        assert result.get("outcome") == "win"

    async def test_builds_prompt(self, engine, sample_trade, mock_prompt_builder):
        await engine.post_trade_reflection(sample_trade)
        mock_prompt_builder.build_post_trade_prompt.assert_called_once()

    async def test_calls_opus_reflect(self, engine, sample_trade, mock_opus):
        await engine.post_trade_reflection(sample_trade)
        mock_opus.reflect_trade.assert_awaited_once()

    async def test_saves_reflection_log(self, engine, sample_trade, mock_reflection_repo):
        await engine.post_trade_reflection(sample_trade)
        mock_reflection_repo.save.assert_awaited_once()
        call_args = mock_reflection_repo.save.call_args[0][0]
        assert call_args["reflection_type"] == "post_trade"

    async def test_updates_trade_with_review(self, engine, sample_trade, mock_trade_repo):
        await engine.post_trade_reflection(sample_trade)
        mock_trade_repo.update.assert_awaited_once()
        call_args = mock_trade_repo.update.call_args
        assert call_args[0][0] == "t-1"
        assert "self_review" in call_args[0][1]

    async def test_handles_opus_error(self, engine, sample_trade, mock_opus):
        """Should handle Opus error gracefully and return empty review."""
        mock_opus.reflect_trade = AsyncMock(return_value=TradeReview())
        result = await engine.post_trade_reflection(sample_trade)
        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# periodic_deep_reflection()
# ---------------------------------------------------------------------------


class TestPeriodicDeepReflection:
    async def test_returns_result_dict(self, engine, mock_reflection_repo):
        trades = [_make_trade(100), _make_trade(-50), _make_trade(80)]
        mock_reflection_repo.get_trades_since_last.return_value = trades
        result = await engine.periodic_deep_reflection()
        assert isinstance(result, dict)
        assert "summary" in result

    async def test_calls_opus_deep_reflect(self, engine, mock_opus, mock_reflection_repo):
        trades = [_make_trade(100), _make_trade(-50)]
        mock_reflection_repo.get_trades_since_last.return_value = trades
        await engine.periodic_deep_reflection()
        mock_opus.deep_reflect.assert_awaited_once()

    async def test_saves_reflection_log(self, engine, mock_reflection_repo):
        trades = [_make_trade(100)]
        mock_reflection_repo.get_trades_since_last.return_value = trades
        await engine.periodic_deep_reflection()
        mock_reflection_repo.save.assert_awaited_once()
        call_args = mock_reflection_repo.save.call_args[0][0]
        assert call_args["reflection_type"] == "deep"

    async def test_applies_playbook_update(self, engine, mock_playbook_mgr, mock_reflection_repo):
        trades = [_make_trade(100)]
        mock_reflection_repo.get_trades_since_last.return_value = trades
        await engine.periodic_deep_reflection()
        mock_playbook_mgr.save_version.assert_awaited_once()

    async def test_publishes_alert(self, engine, mock_redis, mock_reflection_repo):
        trades = [_make_trade(100)]
        mock_reflection_repo.get_trades_since_last.return_value = trades
        await engine.periodic_deep_reflection()
        mock_redis.publish.assert_awaited_once()

    async def test_no_trades_returns_empty(self, engine, mock_reflection_repo):
        """Should return empty result when no trades to reflect on."""
        mock_reflection_repo.get_trades_since_last.return_value = []
        result = await engine.periodic_deep_reflection()
        assert isinstance(result, dict)
        assert result.get("summary", "") == "" or "no trades" in result.get("summary", "").lower()


# ---------------------------------------------------------------------------
# _compute_performance_summary()
# ---------------------------------------------------------------------------


class TestComputePerformanceSummary:
    def test_basic_metrics(self, engine):
        trades = [
            _make_trade(100),
            _make_trade(80),
            _make_trade(-50),
            _make_trade(120),
            _make_trade(-30),
        ]
        result = engine._compute_performance_summary(trades)
        assert result["total_trades"] == 5
        assert result["win_rate"] == pytest.approx(0.6)
        assert result["total_pnl_usd"] == pytest.approx(220.0)

    def test_profit_factor(self, engine):
        trades = [_make_trade(100), _make_trade(80), _make_trade(-50)]
        result = engine._compute_performance_summary(trades)
        # profit_factor = sum(wins) / abs(sum(losses)) = 180 / 50 = 3.6
        assert result["profit_factor"] == pytest.approx(3.6)

    def test_all_wins(self, engine):
        trades = [_make_trade(100), _make_trade(80)]
        result = engine._compute_performance_summary(trades)
        assert result["win_rate"] == pytest.approx(1.0)
        assert result["avg_loss"] == pytest.approx(0.0)
        # profit_factor should be inf or very large
        assert result["profit_factor"] > 100

    def test_all_losses(self, engine):
        trades = [_make_trade(-100), _make_trade(-80)]
        result = engine._compute_performance_summary(trades)
        assert result["win_rate"] == pytest.approx(0.0)
        assert result["avg_win"] == pytest.approx(0.0)
        assert result["profit_factor"] == pytest.approx(0.0)

    def test_single_trade(self, engine):
        trades = [_make_trade(100)]
        result = engine._compute_performance_summary(trades)
        assert result["total_trades"] == 1
        assert result["win_rate"] == pytest.approx(1.0)

    def test_empty_trades(self, engine):
        result = engine._compute_performance_summary([])
        assert result["total_trades"] == 0
        assert result["win_rate"] == pytest.approx(0.0)

    def test_breakdown_by_strategy(self, engine):
        trades = [
            _make_trade(100, strategy="momentum"),
            _make_trade(-50, strategy="momentum"),
            _make_trade(80, strategy="mean_reversion"),
        ]
        result = engine._compute_performance_summary(trades)
        by_strategy = result["by_strategy"]
        assert "momentum" in by_strategy
        assert "mean_reversion" in by_strategy
        assert by_strategy["momentum"]["trades"] == 2
        assert by_strategy["mean_reversion"]["trades"] == 1

    def test_breakdown_by_regime(self, engine):
        trades = [
            _make_trade(100, regime="trending_up"),
            _make_trade(-50, regime="ranging"),
            _make_trade(80, regime="trending_up"),
        ]
        result = engine._compute_performance_summary(trades)
        by_regime = result["by_regime"]
        assert "trending_up" in by_regime
        assert "ranging" in by_regime
        assert by_regime["trending_up"]["trades"] == 2


# ---------------------------------------------------------------------------
# _apply_playbook_update()
# ---------------------------------------------------------------------------


class TestApplyPlaybookUpdate:
    async def test_saves_new_version(self, engine, mock_playbook_mgr):
        result = DeepReflectionResult(
            updated_playbook=Playbook(version=2),
            summary="Updated playbook",
        )
        await engine._apply_playbook_update(result)
        mock_playbook_mgr.save_version.assert_awaited_once()
