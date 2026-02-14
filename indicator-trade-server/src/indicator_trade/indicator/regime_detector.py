"""Market regime classification."""

from __future__ import annotations

import pandas as pd
import structlog

from indicator_trade.models.indicator_set import IndicatorSet

logger = structlog.get_logger()


class RegimeDetector:
    """
    Market Regime Detection using 4H timeframe data:

    | Condition                          | Regime        |
    |------------------------------------|---------------|
    | ADX > 25 AND EMA20 slope > 0.2%   | trending_up   |
    | ADX > 25 AND EMA20 slope < -0.2%  | trending_down |
    | ATR ratio > 1.5 (vs 20-period avg)| volatile      |
    | Otherwise                          | ranging       |
    """

    ADX_THRESHOLD = 25.0
    SLOPE_THRESHOLD = 0.002
    ATR_RATIO_THRESHOLD = 1.5

    def detect(self, candles_4h: pd.DataFrame, indicators: IndicatorSet) -> str:
        """Returns: 'trending_up' | 'trending_down' | 'ranging' | 'volatile'"""
        adx = indicators.adx if indicators.adx is not None else 0.0

        # Compute ATR ratio: current ATR / 20-period average ATR
        atr_ratio = 1.0
        if indicators.atr is not None and len(candles_4h) >= 20:
            high = candles_4h["high"]
            low = candles_4h["low"]
            close = candles_4h["close"]
            tr = pd.concat(
                [
                    high - low,
                    (high - close.shift(1)).abs(),
                    (low - close.shift(1)).abs(),
                ],
                axis=1,
            ).max(axis=1)
            atr_avg = tr.rolling(20).mean().iloc[-1]
            if atr_avg > 0:
                atr_ratio = indicators.atr / atr_avg

        # Compute EMA20 slope: percentage change over last 5 periods
        ema_slope = 0.0
        if 20 in indicators.ema and len(candles_4h) >= 25:
            import pandas_ta as ta

            ema20 = ta.ema(candles_4h["close"], length=20)
            if ema20 is not None and len(ema20.dropna()) >= 5:
                ema_clean = ema20.dropna()
                ema_slope = (ema_clean.iloc[-1] - ema_clean.iloc[-5]) / ema_clean.iloc[-5]

        return self._classify(adx, atr_ratio, ema_slope)

    def _classify(self, adx: float, atr_ratio: float, ema_slope: float) -> str:
        # Trending takes precedence over volatile
        if adx > self.ADX_THRESHOLD and ema_slope > self.SLOPE_THRESHOLD:
            return "trending_up"
        if adx > self.ADX_THRESHOLD and ema_slope < -self.SLOPE_THRESHOLD:
            return "trending_down"
        if atr_ratio > self.ATR_RATIO_THRESHOLD:
            return "volatile"
        return "ranging"
