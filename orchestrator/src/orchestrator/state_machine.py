"""Orchestrator state machine + main loop."""

from __future__ import annotations

import asyncio
import enum
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

import structlog

from orchestrator.models.messages import StreamMessage, SystemAlertMessage

if TYPE_CHECKING:
    from orchestrator.config import Settings
    from orchestrator.db.repository import (
        ReflectionRepository,
        RiskRejectionRepository,
        ScreenerLogRepository,
        TradeRepository,
    )
    from orchestrator.news_scheduler import NewsScheduler
    from orchestrator.playbook_manager import PlaybookManager
    from orchestrator.redis_client import RedisClient
    from orchestrator.risk_gate import RiskGate

logger = structlog.get_logger()


class OrchestratorState(enum.Enum):
    IDLE = "idle"
    COLLECTING = "collecting"
    SCREENING = "screening"
    RESEARCHING = "researching"
    ANALYZING = "analyzing"
    RISK_CHECK = "risk_check"
    EXECUTING = "executing"
    CONFIRMING = "confirming"
    JOURNALING = "journaling"
    REFLECTING = "reflecting"
    HALTED = "halted"
    COOLDOWN = "cooldown"


class Orchestrator:
    def __init__(self, settings: Settings, redis: RedisClient) -> None:
        self.settings = settings
        self.redis = redis
        self.state = OrchestratorState.IDLE
        self.running = False
        self.cooldown_until: datetime | None = None

        # These are injected after construction or in start()
        self.risk_gate: RiskGate | None = None
        self.playbook_manager: PlaybookManager | None = None
        self.trade_repo: TradeRepository | None = None
        self.reflection_repo: ReflectionRepository | None = None
        self.screener_repo: ScreenerLogRepository | None = None
        self.risk_rejection_repo: RiskRejectionRepository | None = None
        self.news_scheduler: NewsScheduler | None = None

    def _set_state(self, new_state: OrchestratorState) -> None:
        """Update state with logging."""
        old = self.state
        self.state = new_state
        logger.info("state_transition", old=old.value, new=new_state.value)

    async def start(self) -> None:
        """Initialize all components, start Redis subscriptions, run main_loop."""
        await self.redis.connect()
        self.running = True
        logger.info("orchestrator_started")
        await self.main_loop()

    async def stop(self) -> None:
        """Graceful shutdown: close connections, flush pending writes."""
        self.running = False
        logger.info("orchestrator_stopped")

    async def main_loop(self) -> None:
        """
        Main decision loop every DECISION_CYCLE_SECONDS:
        1. COLLECTING  — read snapshot, positions, account from Redis
        2. SCREENING   — Haiku pre-filter (if not bypass)
        3. RESEARCHING — Perplexity (if needed)
        4. ANALYZING   — Opus full analysis
        5. RISK_CHECK  — Risk gate validation
        6. EXECUTING   — send order via Redis trade:orders
        7. CONFIRMING  — wait for fill from trade:fills
        8. JOURNALING  — save to DB
        9. REFLECTING  — self-reflection (if conditions met)
        """
        while self.running:
            for instrument in self.settings.INSTRUMENTS:
                try:
                    await self._run_cycle(instrument)
                except Exception:
                    logger.exception("cycle_error", instrument=instrument)
            if self.running:
                await asyncio.sleep(self.settings.DECISION_CYCLE_SECONDS)

    async def _run_cycle(self, instrument: str) -> None:
        """Run a single decision cycle for one instrument."""
        # Skip if halted
        if self.state == OrchestratorState.HALTED:
            return

        # Skip if in cooldown and not expired
        if self.state == OrchestratorState.COOLDOWN:
            if self.cooldown_until and datetime.now(timezone.utc) < self.cooldown_until:
                return
            # Cooldown expired, reset
            self.cooldown_until = None
            self._set_state(OrchestratorState.IDLE)

        # --- 1. COLLECTING ---
        self._set_state(OrchestratorState.COLLECTING)
        snapshot_msg = await self.redis.read_latest("market:snapshots")
        if snapshot_msg is None:
            logger.debug("no_snapshot_available", instrument=instrument)
            self._set_state(OrchestratorState.IDLE)
            return

        snapshot = snapshot_msg.payload
        positions: list = []  # Would come from trade:positions in Phase 4
        account: dict = {"equity": 10000.0}  # Stub — replaced in Phase 4

        # --- 2. SCREENING (stub: always pass) ---
        self._set_state(OrchestratorState.SCREENING)
        bypass = self._should_bypass_screener(snapshot, positions)
        if not bypass and self.settings.SCREENER_ENABLED:
            # Stub: Haiku screener returns signal=True (replaced in Phase 4)
            screen_signal = True
            if self.screener_repo:
                await self.screener_repo.log({
                    "symbol": instrument,
                    "signal": screen_signal,
                    "reason": "stub_screener",
                    "snapshot_json": snapshot,
                    "tokens_used": 0,
                    "latency_ms": 0,
                })
            if not screen_signal:
                self._set_state(OrchestratorState.IDLE)
                return

        # --- 3. RESEARCHING (stub: skip) ---
        self._set_state(OrchestratorState.RESEARCHING)
        research_context = None
        if self._should_research(snapshot):
            # Stub: Perplexity call (replaced in Phase 4)
            research_context = {"summary": "stub_research"}

        # --- 4. ANALYZING (stub: HOLD) ---
        self._set_state(OrchestratorState.ANALYZING)
        # Stub: Opus returns HOLD (replaced in Phase 4)
        opus_decision = {
            "action": "HOLD",
            "symbol": instrument,
            "size_pct": 0.0,
            "entry_price": 0.0,
            "stop_loss": 0.0,
            "take_profit": 0.0,
            "leverage": 1.0,
            "confidence": 0.0,
            "strategy_used": "",
            "reasoning": "Stub: default HOLD",
        }

        action = opus_decision.get("action", "HOLD")

        # --- 5. RISK_CHECK ---
        if action != "HOLD":
            self._set_state(OrchestratorState.RISK_CHECK)
            if self.risk_gate:
                risk_result = self.risk_gate.validate(opus_decision, account, positions)
                if not risk_result.approved:
                    if self.risk_rejection_repo:
                        await self.risk_rejection_repo.log(
                            decision=opus_decision,
                            failed_rules=[f.rule for f in risk_result.failures],
                            account_state=account,
                        )
                    # Check if daily loss or drawdown -> HALT
                    halt_rules = {"daily_loss", "max_drawdown"}
                    failed_rules = {f.rule for f in risk_result.failures}
                    if failed_rules & halt_rules:
                        await self._handle_halt(
                            f"Risk gate halt: {failed_rules & halt_rules}"
                        )
                        return
                    # Check if cooldown
                    if "cooldown" in failed_rules:
                        await self._handle_cooldown()
                        return
                    self._set_state(OrchestratorState.IDLE)
                    return

            # --- 6. EXECUTING (stub: skip actual order) ---
            self._set_state(OrchestratorState.EXECUTING)
            logger.info("stub_execute", action=action, instrument=instrument)

            # --- 7. CONFIRMING (stub: skip) ---
            self._set_state(OrchestratorState.CONFIRMING)

            # --- 8. JOURNALING (stub: skip) ---
            self._set_state(OrchestratorState.JOURNALING)

        # --- 9. REFLECTING ---
        if await self._should_reflect():
            self._set_state(OrchestratorState.REFLECTING)
            # Stub: reflection (replaced in Phase 4)
            logger.info("stub_reflect")

        self._set_state(OrchestratorState.IDLE)

    def _should_bypass_screener(self, snapshot: dict, positions: list) -> bool:
        """Return True if should bypass Haiku and go directly to Opus."""
        # Bypass if open positions exist
        if positions and self.settings.SCREENER_BYPASS_ON_POSITION:
            return True

        # Bypass if in news window
        if (
            self.settings.SCREENER_BYPASS_ON_NEWS
            and self.news_scheduler
            and self.news_scheduler.is_news_window()
        ):
            return True

        # Bypass on market anomaly (>3% price change in 1h)
        price_change = abs(snapshot.get("price_change_1h", 0.0))
        if price_change > 0.03:
            return True

        # Bypass on funding spike (>0.05%)
        funding = abs(snapshot.get("funding_rate", 0.0))
        if funding > 0.0005:
            return True

        return False

    def _should_research(self, snapshot: dict) -> bool:
        """Return True if should call Perplexity."""
        # Research on news window
        if self.news_scheduler and self.news_scheduler.is_news_window():
            return True

        # Research on price anomaly (>3%)
        if abs(snapshot.get("price_change_1h", 0.0)) > 0.03:
            return True

        # Research on funding spike (>0.05%)
        if abs(snapshot.get("funding_rate", 0.0)) > 0.0005:
            return True

        # Research on OI change (>10%)
        if abs(snapshot.get("oi_change_4h", 0.0)) > 0.10:
            return True

        return False

    async def _should_reflect(self) -> bool:
        """Return True if trades since last reflection >= 20 or hours >= 6."""
        if not self.reflection_repo:
            return False

        trades = await self.reflection_repo.get_trades_since_last()
        if len(trades) == 0:
            return False

        # Check trade count threshold
        if len(trades) >= self.settings.REFLECTION_INTERVAL_TRADES:
            return True

        # Check time threshold
        last_time = await self.reflection_repo.get_last_time()
        if last_time is None:
            return True  # Never reflected before, but has trades

        hours_since = (datetime.now(timezone.utc) - last_time).total_seconds() / 3600
        if hours_since >= self.settings.REFLECTION_INTERVAL_HOURS:
            return True

        return False

    async def _handle_halt(self, reason: str) -> None:
        """Set state=HALTED, publish system:alerts, log to DB."""
        self._set_state(OrchestratorState.HALTED)
        self.running = False
        alert = SystemAlertMessage(
            source="orchestrator",
            payload={"reason": reason, "severity": "CRITICAL"},
        )
        await self.redis.publish("system:alerts", alert)
        logger.critical("orchestrator_halted", reason=reason)

    async def _handle_cooldown(self) -> None:
        """Set state=COOLDOWN, wait COOLDOWN_AFTER_LOSS_STREAK seconds."""
        self._set_state(OrchestratorState.COOLDOWN)
        self.cooldown_until = datetime.now(timezone.utc) + timedelta(
            seconds=self.settings.COOLDOWN_AFTER_LOSS_STREAK
        )
        logger.warning(
            "cooldown_started",
            seconds=self.settings.COOLDOWN_AFTER_LOSS_STREAK,
            until=self.cooldown_until.isoformat(),
        )

    async def _on_trade_closed(self, trade: dict) -> None:
        """Called when position closed: update trade, reflect, check cooldown."""
        pnl = trade.get("pnl_usd", 0.0)

        # Update risk gate
        if self.risk_gate:
            self.risk_gate.update_on_trade_close(pnl)

            # Check if cooldown was triggered
            if self.risk_gate.cooldown_until is not None:
                await self._handle_cooldown()

        logger.info("trade_closed_processed", trade_id=trade.get("trade_id"), pnl=pnl)
