"""
supertrend.py
-------------
Supertrend (ATR-based) trend-following strategy.
Uses the professional RMA-based ATR and correct band carry-forward logic.
"""
import numpy as np
import pandas as pd
from .base import BaseBacktestStrategy


class SupertrendStrategy(BaseBacktestStrategy):
    """
    Supertrend indicator strategy.

    Long  → price closes above Supertrend line (direction flips to 1)
    Short → price closes below Supertrend line (direction flips to -1)
    """

    @staticmethod
    def _calc_supertrend(df: pd.DataFrame, atr_period: int = 10, factor: float = 3.0) -> pd.DataFrame:
        df = df.copy()

        hl2 = (df["high"] + df["low"]) / 2

        # True Range
        prev_close = df["close"].shift(1)
        tr = pd.concat([
            df["high"] - df["low"],
            (df["high"] - prev_close).abs(),
            (df["low"] - prev_close).abs()
        ], axis=1).max(axis=1)

        # ATR using RMA (Wilder's smoothing) — same as TradingView
        atr = tr.ewm(alpha=1 / atr_period, adjust=False).mean()

        # Basic bands
        upperband = hl2 + factor * atr
        lowerband = hl2 - factor * atr

        # Final bands with carry-forward logic
        final_upper = upperband.copy()
        final_lower = lowerband.copy()

        for i in range(1, len(df)):
            # Final Upper Band
            if upperband.iloc[i] < final_upper.iloc[i - 1] or df["close"].iloc[i - 1] > final_upper.iloc[i - 1]:
                final_upper.iloc[i] = upperband.iloc[i]
            else:
                final_upper.iloc[i] = final_upper.iloc[i - 1]

            # Final Lower Band
            if lowerband.iloc[i] > final_lower.iloc[i - 1] or df["close"].iloc[i - 1] < final_lower.iloc[i - 1]:
                final_lower.iloc[i] = lowerband.iloc[i]
            else:
                final_lower.iloc[i] = final_lower.iloc[i - 1]

        # Supertrend value and direction
        supertrend = pd.Series(index=df.index, dtype=float)
        direction = pd.Series(index=df.index, dtype=float)

        for i in range(1, len(df)):
            if supertrend.iloc[i - 1] == final_upper.iloc[i - 1]:
                # Previous supertrend was upper band (bearish)
                if df["close"].iloc[i] <= final_upper.iloc[i]:
                    supertrend.iloc[i] = final_upper.iloc[i]
                    direction.iloc[i] = -1
                else:
                    supertrend.iloc[i] = final_lower.iloc[i]
                    direction.iloc[i] = 1
            else:
                # Previous supertrend was lower band (bullish)
                if df["close"].iloc[i] >= final_lower.iloc[i]:
                    supertrend.iloc[i] = final_lower.iloc[i]
                    direction.iloc[i] = 1
                else:
                    supertrend.iloc[i] = final_upper.iloc[i]
                    direction.iloc[i] = -1

        df["supertrend"] = supertrend
        df["st_direction"] = direction

        return df

    # ── Signal generation ──────────────────────────────────────────────────
    def generate_signals(self, df: pd.DataFrame, params: dict) -> pd.DataFrame:
        atr_period = params.get("atr_period", 10)
        factor = params.get("factor", 3.0)

        df = self._calc_supertrend(df, atr_period=atr_period, factor=factor)

        # Drop rows where supertrend hasn't been initialised
        df = df[df["supertrend"].notna()].copy()

        # Direction change → signal
        df["prev_dir"] = df["st_direction"].shift(1)
        df["signal"] = 0
        df.loc[
            (df["st_direction"] == 1) & (df["prev_dir"] == -1), "signal"
        ] = 1   # BUY
        df.loc[
            (df["st_direction"] == -1) & (df["prev_dir"] == 1), "signal"
        ] = -1  # SELL

        # Compatibility: expose supertrend as 'ema' for dashboard tooltip
        df["ema"] = df["supertrend"]

        return df
