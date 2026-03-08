"""
macd_strategy.py
----------------
MACD Momentum strategy.

Long  → MACD histogram crosses above zero (bullish momentum)
Short → MACD histogram crosses below zero (bearish momentum)
"""
import pandas as pd
from .base import BaseBacktestStrategy


class MACDStrategy(BaseBacktestStrategy):
    """MACD histogram zero-cross strategy matching TradingView logic."""

    def generate_signals(self, df: pd.DataFrame, params: dict) -> pd.DataFrame:
        fast_len = params.get("fast_length", 12)
        slow_len = params.get("slow_length", 26)
        macd_len = params.get("macd_length", 9)

        df = df.copy()

        # MACD = EMA(close, fast) - EMA(close, slow)
        fast_ema = self._calc_ema(df["close"], fast_len)
        slow_ema = self._calc_ema(df["close"], slow_len)
        df["macd_line"] = fast_ema - slow_ema

        # Signal line = EMA(MACD, macd_len)
        df["signal_line"] = self._calc_ema(df["macd_line"].dropna(), macd_len).reindex(df.index)

        # Histogram (delta)
        df["histogram"] = df["macd_line"] - df["signal_line"]

        # Drop warmup NaN rows
        df = df[df["histogram"].notna()].copy()

        df["prev_hist"] = df["histogram"].shift(1)
        df["signal"] = 0

        # Long: histogram crosses above zero (ta.crossover(delta, 0))
        cross_above = (df["histogram"] > 0) & (df["prev_hist"] <= 0)
        # Short: histogram crosses below zero (ta.crossunder(delta, 0))
        cross_below = (df["histogram"] < 0) & (df["prev_hist"] >= 0)

        df.loc[cross_above, "signal"] = 1   # BUY
        df.loc[cross_below, "signal"] = -1  # SELL

        # Compatibility: expose slow EMA as 'ema' for dashboard
        df["ema"] = slow_ema.reindex(df.index)

        return df
