"""
base.py
-------
Base class for backtest strategy implementations.
"""
import pandas as pd
from abc import ABC, abstractmethod

class BaseBacktestStrategy(ABC):
    @abstractmethod
    def generate_signals(self, df: pd.DataFrame, params: dict) -> pd.DataFrame:
        """
        Takes OHLCV dataframe and returns a dataframe with 'signal' column.
        signal: 1 (Long), -1 (Short), 0 (Neutral/Hold)
        """
        pass

    def _calc_ema(self, series: pd.Series, period: int) -> pd.Series:
        import numpy as np
        sma = series.rolling(window=period, min_periods=period).mean()
        seeded = series.astype(float).copy()
        
        first_valid = sma.first_valid_index()
        if first_valid is None:
            return pd.Series(np.nan, index=series.index)
            
        idx = seeded.index.get_loc(first_valid)
        seeded.iloc[:idx] = np.nan
        seeded.iloc[idx] = sma.iloc[idx]
        
        return seeded.ewm(span=period, adjust=False).mean()
