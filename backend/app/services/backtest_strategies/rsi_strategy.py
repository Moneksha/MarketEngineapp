"""
rsi_strategy.py
---------------
RSI Mean Reversion strategy.

Long  → RSI crosses above Oversold level (momentum recovery)
Short → RSI crosses below Overbought level (weakening momentum)
"""
import numpy as np
import pandas as pd
from .base import BaseBacktestStrategy


class RSIStrategy(BaseBacktestStrategy):
    """RSI crossover strategy matching TradingView ta.rsi behaviour."""

    @staticmethod
    def _calc_rsi(series: pd.Series, length: int = 14) -> pd.Series:
        """Wilder-smoothed RSI (identical to TradingView ta.rsi)."""
        delta = series.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)

        # Wilder's smoothing (RMA) — same alpha as TradingView
        avg_gain = gain.ewm(alpha=1 / length, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1 / length, adjust=False).mean()

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def generate_signals(self, df: pd.DataFrame, params: dict) -> pd.DataFrame:
        length = params.get("rsi_length", 14)
        oversold = params.get("oversold", 30)
        overbought = params.get("overbought", 70)

        df = df.copy()
        df["rsi"] = self._calc_rsi(df["close"], length)

        # Drop warmup NaN rows
        df = df[df["rsi"].notna()].copy()

        df["prev_rsi"] = df["rsi"].shift(1)
        df["signal"] = 0

        # Long: RSI crosses above oversold level (ta.crossover)
        cross_above = (df["rsi"] > oversold) & (df["prev_rsi"] <= oversold)
        # Short: RSI crosses below overbought level (ta.crossunder)
        cross_below = (df["rsi"] < overbought) & (df["prev_rsi"] >= overbought)

        df.loc[cross_above, "signal"] = 1   # BUY
        df.loc[cross_below, "signal"] = -1  # SELL

        # Compatibility: expose RSI mid-line as 'ema' for dashboard overlay
        df["ema"] = df["rsi"]

        return df
