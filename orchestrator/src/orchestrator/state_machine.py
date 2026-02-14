"""Orchestrator state machine + main loop."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from orchestrator.config import Settings
    from orchestrator.redis_client import RedisClient

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
        self.consecutive_losses = 0
        self.cooldown_until: datetime | None = None
        self.peak_equity: float = 0.0

    async def start(self) -> None:
        """Initialize all components, start Redis subscriptions, run main_loop."""
        ...

    async def stop(self) -> None:
        """Graceful shutdown: close connections, flush pending writes."""
        self.running = False

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
        ...

    async def _collect_data(self, instrument: str) -> tuple:
        """Read latest snapshot, positions, account from Redis."""
        ...

    def _should_bypass_screener(self, snapshot: dict, positions: list) -> bool:
        """Return True if should bypass Haiku and go directly to Opus."""
        ...

    def _should_research(self, snapshot: dict) -> bool:
        """Return True if should call Perplexity."""
        ...

    async def _should_reflect(self) -> bool:
        """Return True if trades since last reflection >= 20 or hours >= 6."""
        ...

    async def _handle_halt(self, reason: str) -> None:
        """Set state=HALTED, publish system:alerts, log to DB."""
        ...

    async def _handle_cooldown(self) -> None:
        """Set state=COOLDOWN, wait COOLDOWN_AFTER_LOSS_STREAK seconds."""
        ...

    async def _on_trade_closed(self, trade: dict) -> None:
        """Called when position closed: update trade, reflect, check cooldown."""
        ...
