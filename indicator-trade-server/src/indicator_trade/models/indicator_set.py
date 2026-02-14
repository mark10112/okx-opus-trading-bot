"""IndicatorSet (RSI, MACD, BB, etc.) Pydantic models."""

from pydantic import BaseModel


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
