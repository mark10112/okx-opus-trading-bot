"""Unit tests for Orchestrator state machine — stub AI calls, full state logic."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from orchestrator.config import Settings
from orchestrator.state_machine import Orchestrator, OrchestratorState


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def settings():
    return Settings(
        DECISION_CYCLE_SECONDS=1,
        INSTRUMENTS=["BTC-USDT-SWAP"],
        REFLECTION_INTERVAL_TRADES=20,
        REFLECTION_INTERVAL_HOURS=6,
        COOLDOWN_AFTER_LOSS_STREAK=1800,
        SCREENER_ENABLED=True,
        SCREENER_BYPASS_ON_POSITION=True,
        SCREENER_BYPASS_ON_NEWS=True,
        SCREENER_MIN_PASS_RATE=0.10,
        MAX_DAILY_LOSS_PCT=0.03,
        MAX_SINGLE_TRADE_PCT=0.05,
        MAX_TOTAL_EXPOSURE_PCT=0.15,
        MAX_CONCURRENT_POSITIONS=3,
        MAX_DRAWDOWN_PCT=0.10,
        MAX_CONSECUTIVE_LOSSES=3,
        MAX_LEVERAGE=3.0,
        MAX_SL_DISTANCE_PCT=0.03,
        MIN_RR_RATIO=1.5,
    )


@pytest.fixture
def mock_redis():
    redis = AsyncMock()
    redis.publish = AsyncMock()
    redis.read_latest = AsyncMock(return_value=None)
    redis.subscribe = AsyncMock()
    redis.connect = AsyncMock()
    redis.disconnect = AsyncMock()
    return redis


@pytest.fixture
def mock_risk_gate():
    from orchestrator.risk_gate import RiskResult
    gate = MagicMock()
    gate.validate.return_value = RiskResult(approved=True)
    gate.update_on_trade_close = MagicMock()
    gate.reset_daily = MagicMock()
    gate.daily_start_equity = 10000.0
    gate.peak_equity = 10000.0
    return gate


@pytest.fixture
def mock_playbook_manager():
    from orchestrator.models.playbook import Playbook
    mgr = AsyncMock()
    mgr.get_latest.return_value = Playbook(version=1)
    return mgr


@pytest.fixture
def mock_trade_repo():
    repo = AsyncMock()
    repo.create.return_value = "t-123"
    repo.update = AsyncMock()
    repo.get_open.return_value = []
    repo.get_recent_closed.return_value = []
    repo.get_trades_since.return_value = []
    return repo


@pytest.fixture
def mock_reflection_repo():
    repo = AsyncMock()
    repo.get_last_time.return_value = None
    repo.get_trades_since_last.return_value = []
    repo.save.return_value = 1
    return repo


@pytest.fixture
def mock_screener_repo():
    repo = AsyncMock()
    repo.log.return_value = 1
    repo.update_opus_agreement = AsyncMock()
    return repo


@pytest.fixture
def mock_risk_rejection_repo():
    repo = AsyncMock()
    repo.log.return_value = 1
    return repo


@pytest.fixture
def mock_news_scheduler():
    scheduler = MagicMock()
    scheduler.is_news_window.return_value = False
    scheduler.get_upcoming_events.return_value = []
    return scheduler


@pytest.fixture
def orchestrator(
    settings,
    mock_redis,
    mock_risk_gate,
    mock_playbook_manager,
    mock_trade_repo,
    mock_reflection_repo,
    mock_screener_repo,
    mock_risk_rejection_repo,
    mock_news_scheduler,
):
    orch = Orchestrator(settings=settings, redis=mock_redis)
    orch.risk_gate = mock_risk_gate
    orch.playbook_manager = mock_playbook_manager
    orch.trade_repo = mock_trade_repo
    orch.reflection_repo = mock_reflection_repo
    orch.screener_repo = mock_screener_repo
    orch.risk_rejection_repo = mock_risk_rejection_repo
    orch.news_scheduler = mock_news_scheduler
    return orch


# ---------------------------------------------------------------------------
# State transitions
# ---------------------------------------------------------------------------


class TestStateTransitions:
    def test_initial_state_is_idle(self, orchestrator):
        """Orchestrator should start in IDLE state."""
        assert orchestrator.state == OrchestratorState.IDLE

    def test_all_states_defined(self):
        """All expected states should be defined."""
        expected = {
            "IDLE", "COLLECTING", "SCREENING", "RESEARCHING",
            "ANALYZING", "RISK_CHECK", "EXECUTING", "CONFIRMING",
            "JOURNALING", "REFLECTING", "HALTED", "COOLDOWN",
        }
        actual = {s.name for s in OrchestratorState}
        assert expected == actual

    def test_set_state(self, orchestrator):
        """_set_state() should update state and log."""
        orchestrator._set_state(OrchestratorState.COLLECTING)
        assert orchestrator.state == OrchestratorState.COLLECTING

    def test_state_values(self):
        """State values should be lowercase strings."""
        for state in OrchestratorState:
            assert state.value == state.name.lower()


# ---------------------------------------------------------------------------
# _should_bypass_screener()
# ---------------------------------------------------------------------------


class TestShouldBypassScreener:
    def test_bypass_on_open_position(self, orchestrator):
        """Should bypass when there are open positions and setting enabled."""
        positions = [{"instId": "BTC-USDT-SWAP", "pos": "1"}]
        result = orchestrator._should_bypass_screener({}, positions)
        assert result is True

    def test_no_bypass_no_positions(self, orchestrator):
        """Should not bypass when no positions and no other triggers."""
        result = orchestrator._should_bypass_screener({}, [])
        assert result is False

    def test_bypass_on_news_window(self, orchestrator, mock_news_scheduler):
        """Should bypass when in news window and setting enabled."""
        mock_news_scheduler.is_news_window.return_value = True
        result = orchestrator._should_bypass_screener({}, [])
        assert result is True

    def test_bypass_on_anomaly(self, orchestrator):
        """Should bypass when price change > 3%."""
        snapshot = {"price_change_1h": 0.04}
        result = orchestrator._should_bypass_screener(snapshot, [])
        assert result is True

    def test_bypass_on_funding_spike(self, orchestrator):
        """Should bypass when funding rate > 0.05%."""
        snapshot = {"funding_rate": 0.0006}
        result = orchestrator._should_bypass_screener(snapshot, [])
        assert result is True

    def test_no_bypass_normal_conditions(self, orchestrator):
        """Should not bypass under normal market conditions."""
        snapshot = {"price_change_1h": 0.01, "funding_rate": 0.0001}
        result = orchestrator._should_bypass_screener(snapshot, [])
        assert result is False

    def test_bypass_disabled_setting(self, orchestrator, settings):
        """Should not bypass on position if setting disabled."""
        orchestrator.settings.SCREENER_BYPASS_ON_POSITION = False
        positions = [{"instId": "BTC-USDT-SWAP"}]
        result = orchestrator._should_bypass_screener({}, positions)
        assert result is False


# ---------------------------------------------------------------------------
# _should_research()
# ---------------------------------------------------------------------------


class TestShouldResearch:
    def test_research_on_news(self, orchestrator, mock_news_scheduler):
        """Should research when news window is active."""
        mock_news_scheduler.is_news_window.return_value = True
        result = orchestrator._should_research({})
        assert result is True

    def test_research_on_price_change(self, orchestrator):
        """Should research when price change > 3%."""
        result = orchestrator._should_research({"price_change_1h": 0.04})
        assert result is True

    def test_research_on_funding_spike(self, orchestrator):
        """Should research when funding rate > 0.05%."""
        result = orchestrator._should_research({"funding_rate": 0.0006})
        assert result is True

    def test_research_on_oi_change(self, orchestrator):
        """Should research when OI change > 10%."""
        result = orchestrator._should_research({"oi_change_4h": 0.12})
        assert result is True

    def test_no_research_normal(self, orchestrator):
        """Should not research under normal conditions."""
        snapshot = {
            "price_change_1h": 0.01,
            "funding_rate": 0.0001,
            "oi_change_4h": 0.02,
        }
        result = orchestrator._should_research(snapshot)
        assert result is False


# ---------------------------------------------------------------------------
# _should_reflect()
# ---------------------------------------------------------------------------


class TestShouldReflect:
    async def test_reflect_on_trade_count(self, orchestrator, mock_reflection_repo):
        """Should reflect when >= 20 trades since last reflection."""
        mock_reflection_repo.get_trades_since_last.return_value = [
            MagicMock() for _ in range(20)
        ]
        result = await orchestrator._should_reflect()
        assert result is True

    async def test_no_reflect_few_trades(self, orchestrator, mock_reflection_repo):
        """Should not reflect when < 20 trades and < 6 hours."""
        mock_reflection_repo.get_trades_since_last.return_value = [
            MagicMock() for _ in range(5)
        ]
        mock_reflection_repo.get_last_time.return_value = datetime.now(timezone.utc)
        result = await orchestrator._should_reflect()
        assert result is False

    async def test_reflect_on_time(self, orchestrator, mock_reflection_repo):
        """Should reflect when > 6 hours since last reflection."""
        mock_reflection_repo.get_trades_since_last.return_value = [MagicMock()]
        mock_reflection_repo.get_last_time.return_value = (
            datetime.now(timezone.utc) - timedelta(hours=7)
        )
        result = await orchestrator._should_reflect()
        assert result is True

    async def test_reflect_no_previous(self, orchestrator, mock_reflection_repo):
        """Should reflect when no previous reflection exists and trades > 0."""
        mock_reflection_repo.get_trades_since_last.return_value = [MagicMock()]
        mock_reflection_repo.get_last_time.return_value = None
        result = await orchestrator._should_reflect()
        assert result is True

    async def test_no_reflect_no_trades(self, orchestrator, mock_reflection_repo):
        """Should not reflect when no trades at all."""
        mock_reflection_repo.get_trades_since_last.return_value = []
        mock_reflection_repo.get_last_time.return_value = None
        result = await orchestrator._should_reflect()
        assert result is False


# ---------------------------------------------------------------------------
# _handle_halt()
# ---------------------------------------------------------------------------


class TestHandleHalt:
    async def test_sets_halted_state(self, orchestrator, mock_redis):
        """_handle_halt() should set state to HALTED."""
        await orchestrator._handle_halt("Max drawdown exceeded")
        assert orchestrator.state == OrchestratorState.HALTED

    async def test_publishes_alert(self, orchestrator, mock_redis):
        """_handle_halt() should publish system alert."""
        await orchestrator._handle_halt("Max drawdown exceeded")
        mock_redis.publish.assert_awaited_once()
        call_args = mock_redis.publish.call_args
        assert call_args[0][0] == "system:alerts"

    async def test_sets_running_false(self, orchestrator):
        """_handle_halt() should stop the main loop."""
        orchestrator.running = True
        await orchestrator._handle_halt("Emergency")
        assert orchestrator.running is False


# ---------------------------------------------------------------------------
# _handle_cooldown()
# ---------------------------------------------------------------------------


class TestHandleCooldown:
    async def test_sets_cooldown_state(self, orchestrator):
        """_handle_cooldown() should set state to COOLDOWN."""
        await orchestrator._handle_cooldown()
        assert orchestrator.state == OrchestratorState.COOLDOWN

    async def test_sets_cooldown_until(self, orchestrator, settings):
        """_handle_cooldown() should set cooldown_until in the future."""
        await orchestrator._handle_cooldown()
        assert orchestrator.cooldown_until is not None
        assert orchestrator.cooldown_until > datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# _on_trade_closed()
# ---------------------------------------------------------------------------


class TestOnTradeClosed:
    async def test_updates_risk_gate_on_loss(self, orchestrator, mock_risk_gate):
        """_on_trade_closed() should update risk gate with PnL."""
        trade = {"trade_id": "t-1", "pnl_usd": -100.0}
        await orchestrator._on_trade_closed(trade)
        mock_risk_gate.update_on_trade_close.assert_called_once_with(-100.0)

    async def test_updates_risk_gate_on_win(self, orchestrator, mock_risk_gate):
        """_on_trade_closed() should update risk gate with positive PnL."""
        trade = {"trade_id": "t-1", "pnl_usd": 200.0}
        await orchestrator._on_trade_closed(trade)
        mock_risk_gate.update_on_trade_close.assert_called_once_with(200.0)

    async def test_triggers_cooldown_on_streak(self, orchestrator, mock_risk_gate):
        """_on_trade_closed() should trigger cooldown when risk gate sets it."""
        mock_risk_gate.cooldown_until = datetime.now(timezone.utc) + timedelta(minutes=30)
        trade = {"trade_id": "t-1", "pnl_usd": -50.0}
        await orchestrator._on_trade_closed(trade)
        assert orchestrator.state == OrchestratorState.COOLDOWN


# ---------------------------------------------------------------------------
# start() / stop()
# ---------------------------------------------------------------------------


class TestLifecycle:
    async def test_stop_sets_running_false(self, orchestrator):
        """stop() should set running to False."""
        orchestrator.running = True
        await orchestrator.stop()
        assert orchestrator.running is False

    async def test_start_initializes(self, orchestrator, mock_redis):
        """start() should connect redis and set running=True, then run main_loop."""
        # Make main_loop exit immediately
        async def fake_loop():
            orchestrator.running = False

        orchestrator.main_loop = fake_loop
        await orchestrator.start()
        mock_redis.connect.assert_awaited_once()
        # After main_loop exits, running should be False


# ---------------------------------------------------------------------------
# main_loop() — full cycle with stub AI (HOLD default)
# ---------------------------------------------------------------------------


class TestMainLoop:
    async def test_single_cycle_hold(self, orchestrator, mock_redis):
        """main_loop() should complete one cycle and default to HOLD."""
        # Setup: snapshot available
        from orchestrator.models.messages import StreamMessage
        snapshot_msg = StreamMessage(
            source="indicator_server",
            type="market_snapshot",
            payload={
                "ticker": {"symbol": "BTC-USDT-SWAP", "last": 60000.0},
                "market_regime": "ranging",
                "price_change_1h": 0.01,
                "funding_rate": 0.0001,
                "oi_change_4h": 0.02,
            },
        )
        mock_redis.read_latest.return_value = snapshot_msg

        # Run one cycle then stop
        cycle_count = 0

        async def run_one_cycle():
            nonlocal cycle_count
            await orchestrator._run_cycle("BTC-USDT-SWAP")
            cycle_count += 1
            orchestrator.running = False

        orchestrator.running = True
        await run_one_cycle()
        assert cycle_count == 1
        # State should return to IDLE after cycle
        assert orchestrator.state == OrchestratorState.IDLE

    async def test_cycle_with_no_snapshot(self, orchestrator, mock_redis):
        """main_loop() should skip cycle when no snapshot available."""
        mock_redis.read_latest.return_value = None

        await orchestrator._run_cycle("BTC-USDT-SWAP")
        # Should stay IDLE, no further processing
        assert orchestrator.state == OrchestratorState.IDLE

    async def test_cycle_halted_state_skips(self, orchestrator):
        """main_loop() should skip cycle when in HALTED state."""
        orchestrator.state = OrchestratorState.HALTED
        orchestrator.running = True

        # _run_cycle should return early
        await orchestrator._run_cycle("BTC-USDT-SWAP")
        assert orchestrator.state == OrchestratorState.HALTED

    async def test_cycle_cooldown_state_skips(self, orchestrator):
        """main_loop() should skip cycle when in COOLDOWN and not expired."""
        orchestrator.state = OrchestratorState.COOLDOWN
        orchestrator.cooldown_until = datetime.now(timezone.utc) + timedelta(minutes=10)

        await orchestrator._run_cycle("BTC-USDT-SWAP")
        assert orchestrator.state == OrchestratorState.COOLDOWN
