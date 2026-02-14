"""Build prompts for Opus analysis/reflection."""

from __future__ import annotations

import structlog

logger = structlog.get_logger()


class PromptBuilder:
    def build_analysis_prompt(
        self,
        snapshot: dict,
        positions: list,
        account: dict,
        research: dict | None,
        playbook: dict,
        recent_trades: list,
    ) -> str:
        """Build XML-structured prompt for Opus analysis (~3000 tokens)."""
        ...

    def build_post_trade_prompt(
        self, trade: dict, indicators_entry: dict, indicators_exit: dict
    ) -> str:
        """Build prompt for post-trade reflection (~2000 tokens)."""
        ...

    def build_deep_reflection_prompt(self, trades: list, playbook: dict, performance: dict) -> str:
        """Build prompt for periodic deep reflection (~8000 tokens)."""
        ...

    def build_research_query(self, snapshot: dict) -> str:
        """Build contextual query for Perplexity."""
        ...
