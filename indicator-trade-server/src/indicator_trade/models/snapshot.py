"""MarketSnapshot (full) Pydantic model."""

from datetime import datetime, timezone

from pydantic import BaseModel, Field

from indicator_trade.models.candle import Candle
from indicator_trade.models.indicator_set import IndicatorSet
from indicator_trade.models.ticker import Ticker


class OrderBook(BaseModel):
    bids: list[tuple[float, float]] = []
    asks: list[tuple[float, float]] = []
    spread: float = 0.0
    bid_depth: float = 0.0
    ask_depth: float = 0.0


class FundingRate(BaseModel):
    current: float = 0.0
    predicted: float = 0.0
    next_funding_time: datetime | None = None


class OpenInterest(BaseModel):
    oi: float = 0.0
    oi_change_24h: float = 0.0


class MarketSnapshot(BaseModel):
    ticker: Ticker
    candles: dict[str, list[Candle]] = {}
    indicators: dict[str, IndicatorSet] = {}
    orderbook: OrderBook = OrderBook()
    funding_rate: FundingRate = FundingRate()
    open_interest: OpenInterest = OpenInterest()
    long_short_ratio: float = 1.0
    taker_buy_sell_ratio: float = 1.0
    market_regime: str = "ranging"
    price_change_1h: float = 0.0
    oi_change_4h: float = 0.0
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
