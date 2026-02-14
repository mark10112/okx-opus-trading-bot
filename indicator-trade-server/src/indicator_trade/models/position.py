"""Position, AccountState Pydantic models."""

from datetime import datetime, timezone

from pydantic import BaseModel, Field


class Position(BaseModel):
    instId: str
    posSide: str
    pos: float = 0.0
    avgPx: float = 0.0
    upl: float = 0.0
    uplRatio: float = 0.0
    lever: float = 1.0
    liqPx: float = 0.0
    margin: float = 0.0
    mgnRatio: float = 0.0
    uTime: datetime | None = None


class AccountState(BaseModel):
    equity: float = 0.0
    available_balance: float = 0.0
    total_pnl: float = 0.0
    daily_pnl: float = 0.0
    max_drawdown_today: float = 0.0
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
