"""
ema_crossover.py
----------------
Fast EMA vs Slow EMA crossover strategy.
"""
import pandas as pd
from .base import BaseBacktestStrategy

class EMACrossoverStrategy(BaseBacktestStrategy):
    def generate_signals(self, df: pd.DataFrame, params: dict) -> pd.DataFrame:
        fast_period = params.get("fast_ema", 20)
        slow_period = params.get("slow_ema", 50)
        
        df = df.copy()
        df["fast_ema"] = self._calc_ema(df["close"], fast_period)
        df["slow_ema"] = self._calc_ema(df["close"], slow_period)
        
        df["prev_fast"] = df["fast_ema"].shift(1)
        df["prev_slow"] = df["slow_ema"].shift(1)
        
        # Crossover signals
        df["signal"] = 0
        crossed_above = (df["fast_ema"] > df["slow_ema"]) & (df["prev_fast"] <= df["prev_slow"])
        crossed_below = (df["fast_ema"] < df["slow_ema"]) & (df["prev_fast"] >= df["prev_slow"])
        
        df.loc[crossed_above, "signal"] = 1   # BUY
        df.loc[crossed_below, "signal"] = -1  # SELL
        
        # Add 'ema' for compatibility with dashboard overlay if needed
        # In crossover, it usually shows both, but for now we'll put slow_ema as the primary 'ema'
        df["ema"] = df["slow_ema"] 
        
        return df
