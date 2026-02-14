"""OrderRequest, OrderResult Pydantic models."""

from datetime import datetime

from pydantic import BaseModel


class OrderRequest(BaseModel):
    action: str  # OPEN_LONG, OPEN_SHORT, CLOSE, ADD, REDUCE
    symbol: str
    side: str  # buy, sell
    pos_side: str  # long, short
    order_type: str  # market, limit
    size: str
    limit_price: str | None = None
    stop_loss: str | None = None
    take_profit: str | None = None
    leverage: str = "1"
    strategy_used: str = ""
    confidence: float = 0.0
    reasoning: str = ""
    decision_id: str = ""


class OrderResult(BaseModel):
    success: bool
    ord_id: str | None = None
    algo_id: str | None = None
    status: str = ""
    error_code: str | None = None
    error_message: str | None = None
    fill_price: float | None = None
    fill_size: float | None = None
    timestamp: datetime = datetime.utcnow()
