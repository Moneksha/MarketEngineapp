"""
ema_trend.py
------------
Price vs EMA Trend strategy.
"""
import pandas as pd
from .base import BaseBacktestStrategy

class EMATrendStrategy(BaseBacktestStrategy):
    def generate_signals(self, df: pd.DataFrame, params: dict) -> pd.DataFrame:
        ema_period = params.get("ema_period", 20)
        
        df = df.copy()
        df["ema"] = self._calc_ema(df["close"], ema_period)
        df["prev_close"] = df["close"].shift(1)
        df["prev_ema"] = df["ema"].shift(1)
        
        # Crossover signals (calculated on current candle)
        df["signal"] = 0
        crossed_above = (df["close"] > df["ema"]) & (df["prev_close"] <= df["prev_ema"])
        crossed_below = (df["close"] < df["ema"]) & (df["prev_close"] >= df["prev_ema"])
        
        df.loc[crossed_above, "signal"] = 1   # BUY
        df.loc[crossed_below, "signal"] = -1  # SELL
        
        return df
