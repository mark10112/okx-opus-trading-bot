"""OHLCV Pydantic model."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class Candle(BaseModel):
    time: datetime
    symbol: str
    timeframe: str
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
