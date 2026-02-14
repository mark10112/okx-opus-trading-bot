"""Technical indicator calculations using pandas-ta."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pandas_ta as ta
import structlog

from indicator_trade.models.indicator_set import (
    BollingerValues,
    IchimokuValues,
    IndicatorSet,
    MACDValues,
    StochRSIValues,
)

logger = structlog.get_logger()

MIN_ROWS_RSI = 14
MIN_ROWS_MACD = 26
MIN_ROWS_BB = 20
MIN_ROWS_ATR = 14
MIN_ROWS_ADX = 14
MIN_ROWS_STOCHRSI = 17  # 14 RSI + 3 smoothing
MIN_ROWS_ICHIMOKU = 52
MIN_ROWS_EMA200 = 200


class TechnicalIndicators:
    """
    Compute all 12 technical indicators from OHLCV DataFrame:
    RSI(14), MACD(12,26,9), BB(20,2.0), EMA(20,50,200), ATR(14),
    VWAP, ADX(14), StochRSI(14,14,3,3), OBV, Ichimoku(9,26,52),
    Support/Resistance, Volume Profile
    """

    def compute(self, df: pd.DataFrame) -> IndicatorSet:
        """Compute all indicators from OHLCV DataFrame (min 200 rows)."""
        if df.empty:
            return IndicatorSet()

        n = len(df)
        close = df["close"]

        # RSI
        rsi_val = None
        if n >= MIN_ROWS_RSI + 1:
            rsi_series = self._compute_rsi(df)
            last_rsi = rsi_series.dropna()
            if not last_rsi.empty:
                rsi_val = float(last_rsi.iloc[-1])

        # MACD
        macd_vals = None
        macd_signal_str = "neutral"
        if n >= MIN_ROWS_MACD + 1:
            macd_result = self._compute_macd(df)
            if macd_result is not None:
                line, sig, hist = macd_result
                macd_vals = MACDValues(line=line, signal=sig, histogram=hist)
                if hist > 0 and line > sig:
                    macd_signal_str = "bullish"
                elif hist < 0 and line < sig:
                    macd_signal_str = "bearish"

        # Bollinger Bands
        bb_vals = None
        bb_position = "middle"
        if n >= MIN_ROWS_BB + 1:
            bb_result = self._compute_bollinger(df)
            if bb_result is not None:
                upper, middle, lower = bb_result
                bb_vals = BollingerValues(upper=upper, middle=middle, lower=lower)
                last_close = float(close.iloc[-1])
                if last_close > upper:
                    bb_position = "above"
                elif last_close < lower:
                    bb_position = "below"
                elif last_close >= middle:
                    bb_position = "upper_half"
                else:
                    bb_position = "lower_half"

        # EMA
        ema_dict = self._compute_ema(df)
        ema_alignment = "neutral"
        if 20 in ema_dict and 50 in ema_dict and 200 in ema_dict:
            if ema_dict[20] > ema_dict[50] > ema_dict[200]:
                ema_alignment = "bullish"
            elif ema_dict[20] < ema_dict[50] < ema_dict[200]:
                ema_alignment = "bearish"

        # ATR
        atr_val = None
        if n >= MIN_ROWS_ATR + 1:
            atr_series = self._compute_atr(df)
            last_atr = atr_series.dropna()
            if not last_atr.empty:
                atr_val = float(last_atr.iloc[-1])

        # VWAP
        vwap_val = None
        vwap_series = self._compute_vwap(df)
        last_vwap = vwap_series.dropna()
        if not last_vwap.empty:
            vwap_val = float(last_vwap.iloc[-1])

        # ADX
        adx_val = None
        if n >= MIN_ROWS_ADX + 1:
            adx_series = self._compute_adx(df)
            last_adx = adx_series.dropna()
            if not last_adx.empty:
                adx_val = float(last_adx.iloc[-1])

        # StochRSI
        stoch_rsi_vals = None
        if n >= MIN_ROWS_STOCHRSI + 1:
            stoch_result = self._compute_stoch_rsi(df)
            if stoch_result is not None:
                k, d = stoch_result
                stoch_rsi_vals = StochRSIValues(k=k, d=d)

        # OBV
        obv_val = None
        obv_series = self._compute_obv(df)
        last_obv = obv_series.dropna()
        if not last_obv.empty:
            obv_val = float(last_obv.iloc[-1])

        # Ichimoku
        ichimoku_vals = None
        if n >= MIN_ROWS_ICHIMOKU + 1:
            ichi_result = self._compute_ichimoku(df)
            if ichi_result is not None:
                ichimoku_vals = IchimokuValues(**ichi_result)

        # Support/Resistance
        support_levels, resistance_levels = self._compute_support_resistance(df)

        # Volume ratio (current vs 20-period average)
        vol = df["volume"]
        vol_avg = vol.rolling(20).mean()
        volume_ratio = 1.0
        if not vol_avg.dropna().empty and vol_avg.iloc[-1] > 0:
            volume_ratio = float(vol.iloc[-1] / vol_avg.iloc[-1])

        return IndicatorSet(
            rsi=rsi_val,
            macd=macd_vals,
            bollinger=bb_vals,
            ema=ema_dict,
            atr=atr_val,
            vwap=vwap_val,
            adx=adx_val,
            stoch_rsi=stoch_rsi_vals,
            obv=obv_val,
            ichimoku=ichimoku_vals,
            support_levels=support_levels,
            resistance_levels=resistance_levels,
            volume_ratio=volume_ratio,
            bb_position=bb_position,
            ema_alignment=ema_alignment,
            macd_signal=macd_signal_str,
        )

    def _compute_rsi(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        result = ta.rsi(df["close"], length=period)
        return result if result is not None else pd.Series(dtype=float)

    def _compute_macd(
        self, df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9
    ) -> tuple[float, float, float] | None:
        result = ta.macd(df["close"], fast=fast, slow=slow, signal=signal)
        if result is None or result.empty:
            return None
        macd_line = result.iloc[:, 0].dropna()
        macd_hist = result.iloc[:, 1].dropna()
        macd_signal = result.iloc[:, 2].dropna()
        if macd_line.empty or macd_hist.empty or macd_signal.empty:
            return None
        return (
            float(macd_line.iloc[-1]),
            float(macd_signal.iloc[-1]),
            float(macd_hist.iloc[-1]),
        )

    def _compute_bollinger(
        self, df: pd.DataFrame, period: int = 20, std: float = 2.0
    ) -> tuple[float, float, float] | None:
        result = ta.bbands(df["close"], length=period, std=std)
        if result is None or result.empty:
            return None
        # bbands returns: BBL, BBM, BBU, BBB, BBP
        bbl = result.iloc[:, 0].dropna()
        bbm = result.iloc[:, 1].dropna()
        bbu = result.iloc[:, 2].dropna()
        if bbl.empty or bbm.empty or bbu.empty:
            return None
        return float(bbu.iloc[-1]), float(bbm.iloc[-1]), float(bbl.iloc[-1])

    def _compute_ema(
        self, df: pd.DataFrame, periods: list[int] | None = None
    ) -> dict[int, float]:
        if periods is None:
            periods = [20, 50, 200]
        result = {}
        for period in periods:
            if len(df) >= period:
                ema = ta.ema(df["close"], length=period)
                if ema is not None:
                    last = ema.dropna()
                    if not last.empty:
                        result[period] = float(last.iloc[-1])
        return result

    def _compute_atr(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        result = ta.atr(df["high"], df["low"], df["close"], length=period)
        return result if result is not None else pd.Series(dtype=float)

    def _compute_vwap(self, df: pd.DataFrame) -> pd.Series:
        result = ta.vwap(df["high"], df["low"], df["close"], df["volume"])
        return result if result is not None else pd.Series(dtype=float)

    def _compute_adx(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        result = ta.adx(df["high"], df["low"], df["close"], length=period)
        if result is None or result.empty:
            return pd.Series(dtype=float)
        # adx returns: ADX, DMP, DMN — first column is ADX
        return result.iloc[:, 0]

    def _compute_stoch_rsi(self, df: pd.DataFrame) -> tuple[float, float] | None:
        result = ta.stochrsi(df["close"], length=14, rsi_length=14, k=3, d=3)
        if result is None or result.empty:
            return None
        k_series = result.iloc[:, 0].dropna()
        d_series = result.iloc[:, 1].dropna()
        if k_series.empty or d_series.empty:
            return None
        return float(k_series.iloc[-1]), float(d_series.iloc[-1])

    def _compute_obv(self, df: pd.DataFrame) -> pd.Series:
        result = ta.obv(df["close"], df["volume"])
        return result if result is not None else pd.Series(dtype=float)

    def _compute_ichimoku(self, df: pd.DataFrame) -> dict | None:
        result = ta.ichimoku(df["high"], df["low"], df["close"], tenkan=9, kijun=26, senkou=52)
        if result is None:
            return None
        # ichimoku returns a tuple of (ichimoku_df, span_df)
        if isinstance(result, tuple):
            ichi_df = result[0]
        else:
            ichi_df = result
        if ichi_df is None or ichi_df.empty:
            return None
        # Column names: ISA_9, ISB_26, ITS_9, IKS_26, ICS_26
        last = ichi_df.dropna(how="all").iloc[-1] if not ichi_df.dropna(how="all").empty else None
        if last is None:
            return None
        cols = ichi_df.columns.tolist()
        # Map columns: ITS = tenkan, IKS = kijun, ISA = senkou_a, ISB = senkou_b, ICS = chikou
        tenkan = float(last[cols[0]]) if not pd.isna(last[cols[0]]) else 0.0
        kijun = float(last[cols[1]]) if not pd.isna(last[cols[1]]) else 0.0
        # For senkou_a and senkou_b, use span_df if available
        if isinstance(result, tuple) and len(result) > 1 and result[1] is not None:
            span_df = result[1]
            span_last = span_df.dropna(how="all")
            if not span_last.empty:
                span_last = span_last.iloc[-1]
                span_cols = span_df.columns.tolist()
                senkou_a = float(span_last[span_cols[0]]) if not pd.isna(span_last[span_cols[0]]) else 0.0
                senkou_b = float(span_last[span_cols[1]]) if not pd.isna(span_last[span_cols[1]]) else 0.0
            else:
                senkou_a = 0.0
                senkou_b = 0.0
        else:
            senkou_a = 0.0
            senkou_b = 0.0
        # Chikou span = close shifted back 26 periods
        chikou = float(df["close"].iloc[-1])
        return {
            "tenkan": tenkan,
            "kijun": kijun,
            "senkou_a": senkou_a,
            "senkou_b": senkou_b,
            "chikou": chikou,
        }

    def _compute_support_resistance(
        self, df: pd.DataFrame
    ) -> tuple[list[float], list[float]]:
        if len(df) < 5:
            return [], []

        close = df["close"]
        high = df["high"]
        low = df["low"]
        current_price = float(close.iloc[-1])

        levels: list[float] = []

        # Classic pivot points from last completed period
        h = float(high.iloc[-2]) if len(df) >= 2 else float(high.iloc[-1])
        l = float(low.iloc[-2]) if len(df) >= 2 else float(low.iloc[-1])
        c = float(close.iloc[-2]) if len(df) >= 2 else float(close.iloc[-1])
        pivot = (h + l + c) / 3.0
        r1 = 2 * pivot - l
        r2 = pivot + (h - l)
        s1 = 2 * pivot - h
        s2 = pivot - (h - l)
        levels.extend([pivot, r1, r2, s1, s2])

        # Fractal highs/lows (5-bar pattern)
        for i in range(2, len(df) - 2):
            if (
                float(high.iloc[i]) > float(high.iloc[i - 1])
                and float(high.iloc[i]) > float(high.iloc[i - 2])
                and float(high.iloc[i]) > float(high.iloc[i + 1])
                and float(high.iloc[i]) > float(high.iloc[i + 2])
            ):
                levels.append(float(high.iloc[i]))
            if (
                float(low.iloc[i]) < float(low.iloc[i - 1])
                and float(low.iloc[i]) < float(low.iloc[i - 2])
                and float(low.iloc[i]) < float(low.iloc[i + 1])
                and float(low.iloc[i]) < float(low.iloc[i + 2])
            ):
                levels.append(float(low.iloc[i]))

        # Sort by proximity to current price
        levels = sorted(set(levels), key=lambda x: abs(x - current_price))

        support = sorted([lv for lv in levels if lv < current_price], reverse=True)[:5]
        resistance = sorted([lv for lv in levels if lv >= current_price])[:5]

        return support, resistance
