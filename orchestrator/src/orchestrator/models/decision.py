"""OpusDecision, AnalysisResult Pydantic models."""

from pydantic import BaseModel


class AnalysisResult(BaseModel):
    market_regime: str = ""
    bias: str = ""
    key_observations: list[str] = []
    risk_factors: list[str] = []


class Decision(BaseModel):
    action: str = "HOLD"  # OPEN_LONG, OPEN_SHORT, CLOSE, ADD, REDUCE, HOLD
    symbol: str = ""
    size_pct: float = 0.0
    entry_price: float | None = None
    stop_loss: float = 0.0
    take_profit: float = 0.0
    order_type: str = "market"
    limit_price: float | None = None


class OpusDecision(BaseModel):
    analysis: AnalysisResult = AnalysisResult()
    decision: Decision = Decision()
    confidence: float = 0.0
    strategy_used: str = ""
    reasoning: str = ""
