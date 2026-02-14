"""TradeRecord, TradeResult Pydantic models."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class TradeRecord(BaseModel):
    trade_id: str = ""
    opened_at: datetime | None = None
    closed_at: datetime | None = None
    duration_seconds: int | None = None
    symbol: str = ""
    direction: str = ""  # LONG, SHORT
    entry_price: Decimal = Decimal("0")
    exit_price: Decimal | None = None
    stop_loss: Decimal = Decimal("0")
    take_profit: Decimal | None = None
    size: Decimal = Decimal("0")
    size_pct: float | None = None
    leverage: float = 1.0
    pnl_usd: float | None = None
    pnl_pct: float | None = None
    fees_usd: float | None = None
    strategy_used: str = ""
    confidence_at_entry: float = 0.0
    market_regime: str = ""
    opus_reasoning: str = ""
    indicators_entry: dict | None = None
    indicators_exit: dict | None = None
    research_context: dict | None = None
    self_review: dict | None = None
    exit_reason: str | None = None
    status: str = "open"  # open, closed, cancelled
    okx_order_id: str | None = None
    okx_algo_id: str | None = None
