"""ResearchResult Pydantic model."""

from datetime import datetime

from pydantic import BaseModel


class ResearchResult(BaseModel):
    query: str = ""
    summary: str = ""
    sentiment: str = "neutral"
    impact_level: str = "low"
    time_horizon: str = "medium"
    key_points: list[str] = []
    trading_implication: str = ""
    confidence: float = 0.0
    sources: list[str] = []
    timestamp: datetime = datetime.utcnow()
