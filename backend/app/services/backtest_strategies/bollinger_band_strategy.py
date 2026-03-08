"""
bollinger_band_strategy.py
--------------------------
Bollinger Band Mean Reversion strategy.

Long  → price crosses above the lower band (recovery from oversold)
Short → price crosses below the upper band (pullback from overbought)
"""
import pandas as pd
from .base import BaseBacktestStrategy


class BollingerBandStrategy(BaseBacktestStrategy):
    """Bollinger Band mean-reversion strategy matching TradingView logic."""

    def generate_signals(self, df: pd.DataFrame, params: dict) -> pd.DataFrame:
        length = params.get("bb_length", 20)
        mult = params.get("bb_mult", 2.0)

        df = df.copy()

        # Basis = SMA(close, length)
        df["bb_basis"] = df["close"].rolling(window=length, min_periods=length).mean()

        # Standard deviation
        df["bb_std"] = df["close"].rolling(window=length, min_periods=length).std()

        # Upper and lower bands
        df["bb_upper"] = df["bb_basis"] + mult * df["bb_std"]
        df["bb_lower"] = df["bb_basis"] - mult * df["bb_std"]

        # Drop warmup NaN rows
        df = df[df["bb_basis"].notna()].copy()

        prev_close = df["close"].shift(1)

        df["signal"] = 0

        # Long: price crosses above lower band (ta.crossover(source, lower))
        cross_above_lower = (df["close"] > df["bb_lower"]) & (prev_close <= df["bb_lower"].shift(1))
        # Short: price crosses below upper band (ta.crossunder(source, upper))
        cross_below_upper = (df["close"] < df["bb_upper"]) & (prev_close >= df["bb_upper"].shift(1))

        df.loc[cross_above_lower, "signal"] = 1   # BUY
        df.loc[cross_below_upper, "signal"] = -1  # SELL

        # Compatibility: expose basis (SMA) as 'ema' for dashboard
        df["ema"] = df["bb_basis"]

        return df
