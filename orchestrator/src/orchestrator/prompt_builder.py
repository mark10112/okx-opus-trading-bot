"""Build prompts for Opus analysis/reflection."""

from __future__ import annotations

import json

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
        ticker = snapshot.get("ticker", {})
        regime = snapshot.get("market_regime", "unknown")
        funding = snapshot.get("funding_rate", {})
        oi = snapshot.get("open_interest", {})
        orderbook = snapshot.get("orderbook", {})

        parts = []

        # --- Market Snapshot ---
        parts.append("<market_snapshot>")
        parts.append(f"Symbol: {ticker.get('symbol', 'N/A')}")
        parts.append(f"Price: {ticker.get('last', 0.0)}")
        parts.append(f"Bid: {ticker.get('bid', 0.0)} | Ask: {ticker.get('ask', 0.0)}")
        parts.append(f"Regime: {regime}")
        parts.append(f"Price Change 1H: {snapshot.get('price_change_1h', 0.0):.4f}")
        parts.append(f"Funding Rate: {funding.get('current', 0.0):.6f} (predicted: {funding.get('predicted', 0.0):.6f})")
        parts.append(f"Open Interest: {oi.get('oi', 0)} (24h change: {oi.get('oi_change_24h', 0.0):.4f})")
        parts.append(f"Long/Short Ratio: {snapshot.get('long_short_ratio', 1.0):.2f}")
        parts.append(f"Orderbook Spread: {orderbook.get('spread', 0.0):.2f}")
        parts.append("</market_snapshot>")

        # --- Technical Indicators ---
        parts.append("<technical_indicators>")
        indicators = snapshot.get("indicators", {})
        for tf, ind in indicators.items():
            parts.append(f"  [{tf}]")
            parts.append(f"  RSI: {ind.get('rsi', 'N/A')}")
            macd = ind.get("macd", {})
            if isinstance(macd, dict):
                parts.append(f"  MACD: line={macd.get('line', 0):.2f} signal={macd.get('signal', 0):.2f} hist={macd.get('histogram', 0):.2f}")
            bb = ind.get("bollinger", {})
            if isinstance(bb, dict):
                parts.append(f"  BB: upper={bb.get('upper', 0):.0f} mid={bb.get('middle', 0):.0f} lower={bb.get('lower', 0):.0f}")
            ema = ind.get("ema", {})
            if ema:
                ema_str = ", ".join(f"EMA{k}={v:.0f}" for k, v in sorted(ema.items(), key=lambda x: int(x[0])))
                parts.append(f"  EMA: {ema_str}")
            parts.append(f"  ATR: {ind.get('atr', 'N/A')} | ADX: {ind.get('adx', 'N/A')}")
            parts.append(f"  BB Position: {ind.get('bb_position', 'N/A')} | EMA Alignment: {ind.get('ema_alignment', 'N/A')} | MACD Signal: {ind.get('macd_signal', 'N/A')}")
        parts.append("</technical_indicators>")

        # --- Current Positions ---
        parts.append("<current_positions>")
        if positions:
            for pos in positions:
                parts.append(f"  {pos.get('instId', 'N/A')} {pos.get('posSide', 'N/A')}: size={pos.get('pos', 0)} avgPx={pos.get('avgPx', 0)} upl={pos.get('upl', 0)} lever={pos.get('lever', 1)}")
        else:
            parts.append("  No open positions")
        parts.append("</current_positions>")

        # --- Account State ---
        parts.append("<account_state>")
        parts.append(f"Equity: {account.get('equity', 0.0):.2f}")
        parts.append(f"Available Balance: {account.get('available_balance', 0.0):.2f}")
        parts.append(f"Daily PnL: {account.get('daily_pnl', 0.0):.2f}")
        parts.append(f"Max Drawdown Today: {account.get('max_drawdown_today', 0.0):.4f}")
        parts.append("</account_state>")

        # --- Research Context ---
        parts.append("<research_context>")
        if research:
            parts.append(f"Summary: {research.get('summary', 'N/A')}")
            parts.append(f"Sentiment: {research.get('sentiment', 'N/A')}")
            parts.append(f"Impact: {research.get('impact_level', 'N/A')}")
            key_points = research.get("key_points", [])
            if key_points:
                for kp in key_points:
                    parts.append(f"  - {kp}")
        else:
            parts.append("  No research available")
        parts.append("</research_context>")

        # --- Playbook ---
        parts.append("<playbook>")
        parts.append(f"Version: {playbook.get('version', 'N/A')}")
        regime_rules = playbook.get("market_regime_rules", {})
        if regime_rules:
            parts.append("Regime Rules:")
            for r_name, r_rule in regime_rules.items():
                preferred = r_rule.get("preferred_strategies", [])
                avoid = r_rule.get("avoid_strategies", [])
                parts.append(f"  {r_name}: prefer={preferred}, avoid={avoid}, max_pos={r_rule.get('max_position_pct', 0)}")
        strategies = playbook.get("strategy_definitions", {})
        if strategies:
            parts.append("Strategies:")
            for s_name, s_def in strategies.items():
                parts.append(f"  {s_name}: entry='{s_def.get('entry', '')}' exit='{s_def.get('exit', '')}'")
        lessons = playbook.get("lessons_learned", [])
        if lessons:
            parts.append("Lessons:")
            for lesson in lessons:
                parts.append(f"  - {lesson.get('lesson', '')} (impact: {lesson.get('impact', 'N/A')})")
        parts.append("</playbook>")

        # --- Recent Trades ---
        parts.append("<recent_trades>")
        if recent_trades:
            for t in recent_trades:
                parts.append(f"  {t.get('trade_id', 'N/A')}: {t.get('direction', 'N/A')} {t.get('symbol', 'N/A')} | PnL: {t.get('pnl_usd', 0):.2f} ({t.get('pnl_pct', 0):.3f}) | strategy={t.get('strategy_used', 'N/A')} conf={t.get('confidence_at_entry', 0):.2f}")
        else:
            parts.append("  No recent trades")
        parts.append("</recent_trades>")

        # --- Output Format ---
        parts.append("<output_format>")
        parts.append("Respond with a single JSON object:")
        parts.append(json.dumps({
            "analysis": {
                "market_regime": "trending_up|trending_down|volatile|ranging",
                "bias": "bullish|bearish|neutral",
                "key_observations": ["..."],
                "risk_factors": ["..."],
            },
            "decision": {
                "action": "OPEN_LONG|OPEN_SHORT|CLOSE|ADD|REDUCE|HOLD",
                "symbol": "BTC-USDT-SWAP",
                "size_pct": 0.03,
                "entry_price": 60000.0,
                "stop_loss": 58500.0,
                "take_profit": 63000.0,
                "order_type": "market|limit",
                "limit_price": None,
            },
            "confidence": 0.75,
            "strategy_used": "momentum|mean_reversion|breakout|scalp",
            "reasoning": "Detailed reasoning for the decision...",
        }, indent=2))
        parts.append("</output_format>")

        return "\n".join(parts)

    def build_post_trade_prompt(
        self, trade: dict, indicators_entry: dict, indicators_exit: dict
    ) -> str:
        """Build prompt for post-trade reflection (~2000 tokens)."""
        parts = []

        parts.append("<completed_trade>")
        parts.append(f"Trade ID: {trade.get('trade_id', 'N/A')}")
        parts.append(f"Symbol: {trade.get('symbol', 'N/A')}")
        parts.append(f"Direction: {trade.get('direction', 'N/A')}")
        parts.append(f"Entry Price: {trade.get('entry_price', 0.0)}")
        parts.append(f"Exit Price: {trade.get('exit_price', 0.0)}")
        parts.append(f"Stop Loss: {trade.get('stop_loss', 0.0)}")
        parts.append(f"Take Profit: {trade.get('take_profit', 0.0)}")
        parts.append(f"PnL USD: {trade.get('pnl_usd', 0.0):.2f}")
        parts.append(f"PnL %: {trade.get('pnl_pct', 0.0):.4f}")
        parts.append(f"Strategy: {trade.get('strategy_used', 'N/A')}")
        parts.append(f"Confidence at Entry: {trade.get('confidence_at_entry', 0.0):.2f}")
        parts.append(f"Market Regime: {trade.get('market_regime', 'N/A')}")
        parts.append(f"Leverage: {trade.get('leverage', 1.0)}")
        parts.append(f"Size %: {trade.get('size_pct', 0.0)}")
        parts.append(f"Duration: {trade.get('duration_seconds', 0)}s")
        parts.append("")
        parts.append("Indicators at Entry:")
        for k, v in indicators_entry.items():
            parts.append(f"  {k}: {v}")
        parts.append("")
        parts.append("Indicators at Exit:")
        for k, v in indicators_exit.items():
            parts.append(f"  {k}: {v}")
        parts.append("</completed_trade>")

        parts.append("")
        parts.append("<output_format>")
        parts.append("Respond with a single JSON object:")
        parts.append(json.dumps({
            "outcome": "win|loss|breakeven",
            "execution_quality": "excellent|good|fair|poor",
            "entry_timing": "early|good|late|missed",
            "exit_timing": "early|good|late|stopped_out",
            "what_went_right": ["..."],
            "what_went_wrong": ["..."],
            "lesson": "Key takeaway from this trade",
            "should_update_playbook": False,
            "playbook_suggestion": "null or suggestion string",
        }, indent=2))
        parts.append("</output_format>")

        return "\n".join(parts)

    def build_deep_reflection_prompt(self, trades: list, playbook: dict, performance: dict) -> str:
        """Build prompt for periodic deep reflection (~8000 tokens)."""
        parts = []

        # --- Performance Summary ---
        parts.append("<performance_summary>")
        parts.append(f"Total Trades: {performance.get('total_trades', 0)}")
        parts.append(f"Win Rate: {performance.get('win_rate', 0.0):.2%}")
        parts.append(f"Profit Factor: {performance.get('profit_factor', 0.0):.2f}")
        parts.append(f"Sharpe Ratio: {performance.get('sharpe_ratio', 0.0):.2f}")
        parts.append(f"Total PnL USD: {performance.get('total_pnl_usd', 0.0):.2f}")
        parts.append(f"Avg Win: {performance.get('avg_win', 0.0):.2f}")
        parts.append(f"Avg Loss: {performance.get('avg_loss', 0.0):.2f}")
        parts.append("</performance_summary>")

        # --- Breakdown by Strategy ---
        parts.append("<breakdown_by_strategy>")
        by_strategy = performance.get("by_strategy", {})
        for s_name, s_data in by_strategy.items():
            parts.append(f"  {s_name}: trades={s_data.get('trades', 0)} win_rate={s_data.get('win_rate', 0.0):.2%} pnl={s_data.get('pnl', 0.0):.2f}")
        parts.append("</breakdown_by_strategy>")

        # --- Breakdown by Regime ---
        parts.append("<breakdown_by_regime>")
        by_regime = performance.get("by_regime", {})
        for r_name, r_data in by_regime.items():
            parts.append(f"  {r_name}: trades={r_data.get('trades', 0)} win_rate={r_data.get('win_rate', 0.0):.2%} pnl={r_data.get('pnl', 0.0):.2f}")
        parts.append("</breakdown_by_regime>")

        # --- Current Playbook ---
        parts.append("<current_playbook>")
        parts.append(f"Version: {playbook.get('version', 'N/A')}")
        regime_rules = playbook.get("market_regime_rules", {})
        if regime_rules:
            parts.append("Regime Rules:")
            for r_name, r_rule in regime_rules.items():
                parts.append(f"  {r_name}: prefer={r_rule.get('preferred_strategies', [])}, avoid={r_rule.get('avoid_strategies', [])}")
        strategies = playbook.get("strategy_definitions", {})
        if strategies:
            parts.append("Strategies:")
            for s_name, s_def in strategies.items():
                parts.append(f"  {s_name}: entry='{s_def.get('entry', '')}' exit='{s_def.get('exit', '')}'")
        lessons = playbook.get("lessons_learned", [])
        if lessons:
            parts.append("Lessons:")
            for lesson in lessons:
                parts.append(f"  - {lesson.get('lesson', '')}")
        parts.append("</current_playbook>")

        # --- Recent Trades Detail ---
        parts.append("<recent_trades>")
        for t in trades:
            parts.append(f"  {t.get('trade_id', 'N/A')}: {t.get('direction', 'N/A')} {t.get('symbol', 'N/A')} | PnL: {t.get('pnl_usd', 0):.2f} | strategy={t.get('strategy_used', 'N/A')} conf={t.get('confidence_at_entry', 0):.2f}")
        parts.append("</recent_trades>")

        # --- Tasks ---
        parts.append("<tasks>")
        parts.append("1. Identify recurring patterns in wins and losses")
        parts.append("2. Evaluate strategy effectiveness per regime")
        parts.append("3. Check confidence calibration (stated vs actual win rate)")
        parts.append("4. Identify behavioral biases")
        parts.append("5. Propose specific playbook updates with reasoning")
        parts.append("")
        parts.append("Respond with a single JSON object:")
        parts.append(json.dumps({
            "updated_playbook": {
                "version": "incremented",
                "market_regime_rules": {},
                "strategy_definitions": {},
                "lessons_learned": [],
                "confidence_calibration": {},
                "time_filters": {},
            },
            "pattern_insights": ["..."],
            "bias_findings": ["..."],
            "discipline_score": 75,
            "summary": "Overall assessment...",
        }, indent=2))
        parts.append("</tasks>")

        return "\n".join(parts)

    def build_research_query(self, snapshot: dict) -> str:
        """Build contextual query for Perplexity."""
        ticker = snapshot.get("ticker", {})
        symbol = ticker.get("symbol", "BTC-USDT")
        price = ticker.get("last", 0.0)
        regime = snapshot.get("market_regime", "unknown")
        price_change = snapshot.get("price_change_1h", 0.0)
        funding = snapshot.get("funding_rate", {})
        funding_rate = funding.get("current", 0.0) if isinstance(funding, dict) else 0.0

        parts = []
        parts.append(f"Current {symbol} market analysis:")
        parts.append(f"Price: ${price:,.0f}, regime: {regime}, 1H change: {price_change:.2%}")

        if abs(price_change) > 0.03:
            parts.append(f"Significant price movement detected ({price_change:.2%} in 1H).")
            parts.append("What is causing this move? Any breaking news or events?")

        if abs(funding_rate) > 0.0005:
            parts.append(f"Elevated funding rate: {funding_rate:.4%}.")
            parts.append("What is driving the funding rate? Is there a crowded trade?")

        parts.append("What are the key macro and crypto-specific factors affecting BTC price right now?")
        parts.append("Any upcoming events or catalysts in the next 24 hours?")

        return " ".join(parts)
