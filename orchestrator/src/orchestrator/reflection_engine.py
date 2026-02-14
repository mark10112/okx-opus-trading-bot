"""Post-trade + periodic deep reflection."""

from __future__ import annotations

import math
from collections import defaultdict

import structlog

from orchestrator.db.repository import ReflectionRepository, TradeRepository
from orchestrator.models.messages import SystemAlertMessage
from orchestrator.models.reflection import DeepReflectionResult, TradeReview
from orchestrator.opus_client import OpusClient
from orchestrator.playbook_manager import PlaybookManager
from orchestrator.prompt_builder import PromptBuilder
from orchestrator.redis_client import RedisClient

logger = structlog.get_logger()


class ReflectionEngine:
    def __init__(
        self,
        opus: OpusClient,
        playbook_mgr: PlaybookManager,
        prompt_builder: PromptBuilder,
        trade_repo: TradeRepository,
        reflection_repo: ReflectionRepository,
        redis: RedisClient,
    ) -> None:
        self.opus = opus
        self.playbook_mgr = playbook_mgr
        self.prompt_builder = prompt_builder
        self.trade_repo = trade_repo
        self.reflection_repo = reflection_repo
        self.redis = redis

    async def post_trade_reflection(self, trade: dict) -> dict:
        """After every trade close: build prompt, call Opus, save review."""
        indicators_entry = trade.get("indicators_entry", {}) or {}
        indicators_exit = trade.get("indicators_exit", {}) or {}

        prompt = self.prompt_builder.build_post_trade_prompt(
            trade=trade,
            indicators_entry=indicators_entry,
            indicators_exit=indicators_exit,
        )

        review: TradeReview = await self.opus.reflect_trade(prompt)
        review_dict = review.model_dump(mode="json")

        # Update trade record with self-review
        trade_id = trade.get("trade_id")
        if trade_id:
            await self.trade_repo.update(trade_id, {"self_review": review_dict})

        # Save reflection log
        await self.reflection_repo.save({
            "reflection_type": "post_trade",
            "trade_id": trade_id,
            "content_json": review_dict,
        })

        logger.info(
            "post_trade_reflection_complete",
            trade_id=trade_id,
            outcome=review.outcome,
        )
        return review_dict

    async def periodic_deep_reflection(self) -> dict:
        """Every 20 trades or 6 hours: deep analysis, update playbook."""
        # Get trades since last reflection
        trades_records = await self.reflection_repo.get_trades_since_last()
        trades = [self._trade_record_to_dict(t) for t in trades_records]

        if not trades:
            logger.info("deep_reflection_skipped", reason="no trades")
            return {"summary": "No trades to reflect on"}

        # Compute performance
        performance = self._compute_performance_summary(trades)

        # Get current playbook
        playbook = await self.playbook_mgr.get_latest()
        playbook_dict = playbook.model_dump(mode="json")

        # Build prompt and call Opus
        prompt = self.prompt_builder.build_deep_reflection_prompt(
            trades=trades,
            playbook=playbook_dict,
            performance=performance,
        )

        result: DeepReflectionResult = await self.opus.deep_reflect(prompt)
        result_dict = result.model_dump(mode="json")

        # Apply playbook update
        await self._apply_playbook_update(result)

        # Save reflection log
        await self.reflection_repo.save({
            "reflection_type": "deep",
            "content_json": result_dict,
        })

        # Publish alert
        alert = SystemAlertMessage(
            source="orchestrator",
            payload={
                "reason": f"Deep reflection complete: {result.summary[:100]}",
                "severity": "INFO",
                "discipline_score": result.discipline_score,
            },
        )
        await self.redis.publish("system:alerts", alert)

        logger.info(
            "deep_reflection_complete",
            discipline_score=result.discipline_score,
            insights=len(result.pattern_insights),
        )
        return result_dict

    def _compute_performance_summary(self, trades: list) -> dict:
        """Calculate metrics: win rate, profit factor, Sharpe, breakdowns."""
        if not trades:
            return {
                "total_trades": 0,
                "win_rate": 0.0,
                "profit_factor": 0.0,
                "sharpe_ratio": 0.0,
                "total_pnl_usd": 0.0,
                "avg_win": 0.0,
                "avg_loss": 0.0,
                "by_strategy": {},
                "by_regime": {},
            }

        total = len(trades)
        pnls = [t.get("pnl_usd", 0.0) for t in trades]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]

        win_rate = len(wins) / total if total > 0 else 0.0
        total_pnl = sum(pnls)
        avg_win = sum(wins) / len(wins) if wins else 0.0
        avg_loss = sum(losses) / len(losses) if losses else 0.0

        sum_wins = sum(wins)
        sum_losses = abs(sum(losses))
        if sum_losses > 0:
            profit_factor = sum_wins / sum_losses
        elif sum_wins > 0:
            profit_factor = float("inf")
        else:
            profit_factor = 0.0

        # Sharpe ratio (simplified: mean/std of PnL)
        if len(pnls) > 1:
            mean_pnl = total_pnl / total
            variance = sum((p - mean_pnl) ** 2 for p in pnls) / (total - 1)
            std_pnl = math.sqrt(variance) if variance > 0 else 0.0
            sharpe = mean_pnl / std_pnl if std_pnl > 0 else 0.0
        else:
            sharpe = 0.0

        # Breakdown by strategy
        by_strategy: dict[str, dict] = defaultdict(lambda: {"trades": 0, "wins": 0, "pnl": 0.0})
        for t in trades:
            s = t.get("strategy_used", "unknown")
            by_strategy[s]["trades"] += 1
            by_strategy[s]["pnl"] += t.get("pnl_usd", 0.0)
            if t.get("pnl_usd", 0.0) > 0:
                by_strategy[s]["wins"] += 1

        for s_data in by_strategy.values():
            s_data["win_rate"] = s_data["wins"] / s_data["trades"] if s_data["trades"] > 0 else 0.0

        # Breakdown by regime
        by_regime: dict[str, dict] = defaultdict(lambda: {"trades": 0, "wins": 0, "pnl": 0.0})
        for t in trades:
            r = t.get("market_regime", "unknown")
            by_regime[r]["trades"] += 1
            by_regime[r]["pnl"] += t.get("pnl_usd", 0.0)
            if t.get("pnl_usd", 0.0) > 0:
                by_regime[r]["wins"] += 1

        for r_data in by_regime.values():
            r_data["win_rate"] = r_data["wins"] / r_data["trades"] if r_data["trades"] > 0 else 0.0

        return {
            "total_trades": total,
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "sharpe_ratio": sharpe,
            "total_pnl_usd": total_pnl,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "by_strategy": dict(by_strategy),
            "by_regime": dict(by_regime),
        }

    async def _apply_playbook_update(self, result: DeepReflectionResult) -> None:
        """Save new playbook version to DB, log changes."""
        playbook = result.updated_playbook
        await self.playbook_mgr.save_version(
            playbook=playbook,
            change_summary=result.summary,
            triggered_by="deep_reflection",
            performance={},
        )
        logger.info(
            "playbook_updated",
            new_version=playbook.version,
            summary=result.summary[:100],
        )

    @staticmethod
    def _trade_record_to_dict(trade) -> dict:
        """Convert TradeRecord (Pydantic model or dict) to plain dict."""
        if hasattr(trade, "model_dump"):
            return trade.model_dump(mode="json")
        return dict(trade)
