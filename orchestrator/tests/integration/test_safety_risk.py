"""B6: Safety & risk gate integration tests.

Test risk gate with real DB for rejection logging, halt/cooldown flows.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import text

from orchestrator.config import Settings
from orchestrator.db.repository import RiskRejectionRepository
from orchestrator.models.messages import MarketSnapshotMessage, SystemAlertMessage
from orchestrator.redis_client import RedisClient
from orchestrator.risk_gate import RiskGate
from orchestrator.state_machine import Orchestrator, OrchestratorState

from .conftest import TEST_REDIS_URL

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _settings(**overrides) -> Settings:
    defaults = {
        "REDIS_URL": TEST_REDIS_URL,
        "INSTRUMENTS": ["BTC-USDT-SWAP"],
        "DECISION_CYCLE_SECONDS": 1,
        "SCREENER_ENABLED": False,
        "REFLECTION_INTERVAL_TRADES": 999,
    }
    defaults.update(overrides)
    return Settings(**defaults)


def _valid_decision(**overrides) -> dict:
    """A decision that passes all risk checks."""
    base = {
        "action": "OPEN_LONG",
        "symbol": "BTC-USDT-SWAP",
        "size_pct": 0.02,
        "entry_price": 50000.0,
        "stop_loss": 49500.0,
        "take_profit": 51500.0,
        "leverage": 2.0,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# 1. Valid trade passes all risk checks
# ---------------------------------------------------------------------------


async def test_valid_trade_passes_risk_gate(session_factory):
    """A well-formed trade passes all 11 risk checks."""
    settings = _settings()
    gate = RiskGate(settings)
    gate.daily_start_equity = 10000.0
    gate.peak_equity = 10000.0

    account = {"equity": 9800.0, "available_balance": 9800.0}
    positions = []

    result = gate.validate(_valid_decision(), account, positions)
    assert result.approved is True
    assert len(result.failures) == 0


# ---------------------------------------------------------------------------
# 2. Missing stop loss rejected
# ---------------------------------------------------------------------------


async def test_missing_stop_loss_rejected(session_factory):
    """Trade without stop_loss is rejected."""
    settings = _settings()
    gate = RiskGate(settings)

    decision = _valid_decision(stop_loss=0.0)
    account = {"equity": 10000.0}
    positions = []

    result = gate.validate(decision, account, positions)
    assert result.approved is False
    rules = [f.rule for f in result.failures]
    assert "stop_loss" in rules


# ---------------------------------------------------------------------------
# 3. Oversized trade rejected + logged to DB
# ---------------------------------------------------------------------------


async def test_oversized_trade_rejected_and_logged(session_factory, clean_tables):
    """Trade > 5% equity rejected, rejection logged to risk_rejections table."""
    settings = _settings()
    gate = RiskGate(settings)
    repo = RiskRejectionRepository(session_factory)

    decision = _valid_decision(size_pct=0.10)
    account = {"equity": 10000.0}
    positions = []

    result = gate.validate(decision, account, positions)
    assert result.approved is False
    rules = [f.rule for f in result.failures]
    assert "trade_size" in rules

    # Log rejection to DB
    log_id = await repo.log(
        decision=decision,
        failed_rules=rules,
        account_state=account,
    )
    assert log_id > 0

    # Verify in DB
    async with session_factory() as session:
        row = await session.execute(
            text("SELECT failed_rules FROM risk_rejections WHERE id = :id"),
            {"id": log_id},
        )
        data = row.fetchone()
    assert data is not None
    assert "trade_size" in data[0]


# ---------------------------------------------------------------------------
# 4. Max position count rejected
# ---------------------------------------------------------------------------


async def test_max_position_count_rejected(session_factory):
    """3 existing positions -> new trade rejected."""
    settings = _settings()
    gate = RiskGate(settings)

    decision = _valid_decision()
    account = {"equity": 10000.0}
    positions = [
        {"instId": "BTC-USDT-SWAP", "notionalUsd": 500},
        {"instId": "ETH-USDT-SWAP", "notionalUsd": 300},
        {"instId": "SOL-USDT-SWAP", "notionalUsd": 200},
    ]

    result = gate.validate(decision, account, positions)
    assert result.approved is False
    rules = [f.rule for f in result.failures]
    assert "position_count" in rules


# ---------------------------------------------------------------------------
# 5. Daily loss triggers HALT via state machine
# ---------------------------------------------------------------------------


async def test_daily_loss_triggers_halt(session_factory, real_redis, clean_tables):
    """Daily loss > 3% -> state machine halts and publishes system:alerts."""
    settings = _settings()
    redis = RedisClient(redis_url=TEST_REDIS_URL, consumer_group="test_halt", consumer_name="t-1")
    await redis.connect()

    try:
        orch = Orchestrator(settings=settings, redis=redis)
        orch.running = True
        orch.risk_gate = RiskGate(settings)
        orch.risk_gate.daily_start_equity = 10000.0
        orch.risk_gate.peak_equity = 10000.0
        orch.risk_rejection_repo = RiskRejectionRepository(session_factory)

        # Simulate daily loss > 3%
        account = {"equity": 9600.0}  # 4% loss
        decision = _valid_decision()

        result = orch.risk_gate.validate(decision, account, [])
        assert result.approved is False
        rules = [f.rule for f in result.failures]
        assert "daily_loss" in rules

        # Trigger halt via state machine
        await orch._handle_halt("Daily loss limit hit")
        assert orch.state == OrchestratorState.HALTED
        assert orch.running is False

        # System alert published
        alert = await redis.read_latest("system:alerts")
        assert alert is not None
        assert alert.payload["severity"] == "CRITICAL"
    finally:
        await redis.disconnect()


# ---------------------------------------------------------------------------
# 6. Consecutive losses trigger cooldown
# ---------------------------------------------------------------------------


async def test_consecutive_losses_trigger_cooldown(session_factory):
    """3 consecutive losses -> cooldown activated."""
    settings = _settings()
    gate = RiskGate(settings)

    # Simulate 3 consecutive losses
    gate.update_on_trade_close(-50.0)
    assert gate.consecutive_losses == 1
    assert gate.cooldown_until is None

    gate.update_on_trade_close(-30.0)
    assert gate.consecutive_losses == 2
    assert gate.cooldown_until is None

    gate.update_on_trade_close(-20.0)
    assert gate.consecutive_losses == 3
    assert gate.cooldown_until is not None

    # Cooldown should block new trades
    decision = _valid_decision()
    account = {"equity": 10000.0}
    result = gate.validate(decision, account, [])
    assert result.approved is False
    rules = [f.rule for f in result.failures]
    assert "cooldown" in rules


# ---------------------------------------------------------------------------
# 7. HOLD and CLOSE always approved
# ---------------------------------------------------------------------------


async def test_hold_and_close_always_approved(session_factory):
    """HOLD and CLOSE actions skip all risk checks."""
    settings = _settings()
    gate = RiskGate(settings)
    # Even with bad state, HOLD/CLOSE should pass
    gate.cooldown_until = datetime.now(timezone.utc) + timedelta(hours=1)

    account = {"equity": 0.0}  # zero equity
    positions = [{"instId": "X"} for _ in range(10)]  # too many positions

    for action in ["HOLD", "CLOSE"]:
        result = gate.validate({"action": action}, account, positions)
        assert result.approved is True, f"{action} should always be approved"
