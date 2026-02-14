"""Ticker (last, bid, ask, vol) Pydantic model."""

from pydantic import BaseModel


class Ticker(BaseModel):
    symbol: str
    last: float
    bid: float
    ask: float
    volume_24h: float
    change_24h: float
    volume_ratio: float = 1.0
