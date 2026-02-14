"""Technical indicator calculations using pandas-ta."""

from __future__ import annotations

import pandas as pd
import structlog

from indicator_trade.models.indicator_set import IndicatorSet

logger = structlog.get_logger()


class TechnicalIndicators:
    """
    Compute all 12 technical indicators from OHLCV DataFrame:
    RSI(14), MACD(12,26,9), BB(20,2.0), EMA(20,50,200), ATR(14),
    VWAP, ADX(14), StochRSI(14,14,3,3), OBV, Ichimoku(9,26,52),
    Support/Resistance, Volume Profile
    """

    def compute(self, df: pd.DataFrame) -> IndicatorSet:
        """Compute all indicators from OHLCV DataFrame (min 200 rows)."""
        ...

    def _compute_rsi(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        ...

    def _compute_macd(
        self, df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9
    ) -> tuple[float, float, float]:
        ...

    def _compute_bollinger(
        self, df: pd.DataFrame, period: int = 20, std: float = 2.0
    ) -> tuple[float, float, float]:
        ...

    def _compute_ema(
        self, df: pd.DataFrame, periods: list[int] | None = None
    ) -> dict[int, float]:
        ...

    def _compute_atr(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        ...

    def _compute_vwap(self, df: pd.DataFrame) -> pd.Series:
        ...

    def _compute_adx(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        ...

    def _compute_stoch_rsi(self, df: pd.DataFrame) -> tuple[float, float]:
        ...

    def _compute_obv(self, df: pd.DataFrame) -> pd.Series:
        ...

    def _compute_ichimoku(self, df: pd.DataFrame) -> dict:
        ...

    def _compute_support_resistance(
        self, df: pd.DataFrame
    ) -> tuple[list[float], list[float]]:
        ...
