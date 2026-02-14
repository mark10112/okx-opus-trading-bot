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

    def detect(self, candles_4h: pd.DataFrame, indicators: IndicatorSet) -> str:
        """Returns: 'trending_up' | 'trending_down' | 'ranging' | 'volatile'"""
        ...

    def _classify(self, adx: float, atr_ratio: float, ema_slope: float) -> str:
        ...
