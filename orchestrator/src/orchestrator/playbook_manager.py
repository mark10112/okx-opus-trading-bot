"""Playbook CRUD & versioning in DB."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from orchestrator.models.playbook import (
    Playbook,
    RegimeRule,
    StrategyDef,
    TimeFilter,
)

if TYPE_CHECKING:
    from orchestrator.db.repository import PlaybookRepository

logger = structlog.get_logger()


def _default_playbook() -> Playbook:
    """Create default playbook v1 with basic regime rules and strategies."""
    return Playbook(
        version=1,
        market_regime_rules={
            "trending_up": RegimeRule(
                preferred_strategies=["momentum", "breakout"],
                avoid_strategies=["mean_reversion"],
                max_position_pct=0.05,
                preferred_timeframe="1H",
            ),
            "trending_down": RegimeRule(
                preferred_strategies=["momentum", "breakout"],
                avoid_strategies=["mean_reversion"],
                max_position_pct=0.04,
                preferred_timeframe="1H",
            ),
            "volatile": RegimeRule(
                preferred_strategies=["mean_reversion", "scalp"],
                avoid_strategies=["breakout"],
                max_position_pct=0.03,
                preferred_timeframe="5m",
            ),
            "ranging": RegimeRule(
                preferred_strategies=["mean_reversion", "scalp"],
                avoid_strategies=["momentum"],
                max_position_pct=0.03,
                preferred_timeframe="1H",
            ),
        },
        strategy_definitions={
            "momentum": StrategyDef(
                entry="EMA20 > EMA50 > EMA200, RSI 40-70, MACD bullish crossover",
                exit="RSI > 80 or MACD bearish crossover or trailing SL hit",
                filters=["ADX > 25", "Volume above average"],
                historical_winrate=0.0,
                avg_rr=0.0,
            ),
            "mean_reversion": StrategyDef(
                entry="RSI < 30 or > 70, BB touch, price near S/R level",
                exit="RSI returns to 50 or opposite BB touch",
                filters=["ADX < 25", "Ranging regime"],
                historical_winrate=0.0,
                avg_rr=0.0,
            ),
            "breakout": StrategyDef(
                entry="Price breaks key S/R with volume spike",
                exit="Failed breakout (price returns inside range) or TP hit",
                filters=["Volume > 1.5x average", "ADX rising"],
                historical_winrate=0.0,
                avg_rr=0.0,
            ),
            "scalp": StrategyDef(
                entry="StochRSI oversold/overbought on 5m, BB squeeze release",
                exit="Quick TP at 0.5-1% or time-based exit (15 min)",
                filters=["Spread < 0.05%", "Low volatility"],
                historical_winrate=0.0,
                avg_rr=0.0,
            ),
        },
        lessons_learned=[],
        confidence_calibration={},
        time_filters=TimeFilter(),
    )


class PlaybookManager:
    def __init__(self, repo: PlaybookRepository) -> None:
        self.repo = repo

    async def get_latest(self) -> Playbook:
        """Load latest playbook version from DB. Create default if none exists."""
        stored = await self.repo.get_latest()
        if stored is None:
            playbook = _default_playbook()
            await self.save_version(
                playbook=playbook,
                change_summary="Default playbook v1",
                triggered_by="init",
                performance={},
            )
            logger.info("default_playbook_created")
            return playbook
        return Playbook.model_validate(stored["playbook_json"])

    async def save_version(
        self,
        playbook: Playbook,
        change_summary: str,
        triggered_by: str,
        performance: dict,
    ) -> int:
        """Save new version, return version number."""
        data = {
            "version": playbook.version,
            "playbook_json": playbook.model_dump(mode="json"),
            "change_summary": change_summary,
            "triggered_by": triggered_by,
            "performance_at_update": performance,
        }
        version = await self.repo.save_version(data)
        logger.info("playbook_version_saved", version=version, triggered_by=triggered_by)
        return version

    async def get_version(self, version: int) -> Playbook:
        """Load specific version."""
        history = await self.repo.get_history(limit=100)
        for entry in history:
            if entry["version"] == version:
                return Playbook.model_validate(entry["playbook_json"])
        raise ValueError(f"Playbook version {version} not found")

    async def get_history(self, limit: int = 20) -> list[dict]:
        """Get version history with change summaries."""
        return await self.repo.get_history(limit=limit)
