"""MarketSnapshot, IndicatorSet, Ticker — orchestrator-side models."""

from datetime import datetime

from pydantic import BaseModel


class Ticker(BaseModel):
    symbol: str
    last: float
    bid: float
    ask: float
    volume_24h: float
    change_24h: float
    volume_ratio: float = 1.0


class MACDValues(BaseModel):
    line: float
    signal: float
    histogram: float


class BollingerValues(BaseModel):
    upper: float
    middle: float
    lower: float


class StochRSIValues(BaseModel):
    k: float
    d: float


class IchimokuValues(BaseModel):
    tenkan: float
    kijun: float
    senkou_a: float
    senkou_b: float
    chikou: float


class IndicatorSet(BaseModel):
    rsi: float | None = None
    macd: MACDValues | None = None
    bollinger: BollingerValues | None = None
    ema: dict[int, float] = {}
    atr: float | None = None
    vwap: float | None = None
    adx: float | None = None
    stoch_rsi: StochRSIValues | None = None
    obv: float | None = None
    ichimoku: IchimokuValues | None = None
    support_levels: list[float] = []
    resistance_levels: list[float] = []
    volume_ratio: float = 1.0
    bb_position: str = "middle"
    ema_alignment: str = "neutral"
    macd_signal: str = "neutral"


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
    indicators: dict[str, IndicatorSet] = {}
    orderbook: OrderBook = OrderBook()
    funding_rate: FundingRate = FundingRate()
    open_interest: OpenInterest = OpenInterest()
    long_short_ratio: float = 1.0
    taker_buy_sell_ratio: float = 1.0
    market_regime: str = "ranging"
    price_change_1h: float = 0.0
    oi_change_4h: float = 0.0
    timestamp: datetime = datetime.utcnow()
