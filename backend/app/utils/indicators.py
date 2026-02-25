"""
Technical Indicators Library
Provides: EMA, SMA, VWAP, ATR, RSI, Bollinger Bands, EMA Crossover detection
All functions operate on pandas DataFrames or Series for performance.
"""
import pandas as pd
import numpy as np
from typing import Optional


def ema(series: pd.Series, period: int) -> pd.Series:
    """Exponential Moving Average."""
    return series.ewm(span=period, adjust=False).mean()


def sma(series: pd.Series, period: int) -> pd.Series:
    """Simple Moving Average."""
    return series.rolling(window=period).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Relative Strength Index (0-100)."""
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, adjust=False).mean()
    avg_loss = loss.ewm(com=period - 1, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Average True Range."""
    high = df["high"]
    low = df["low"]
    close = df["close"]
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs()
    ], axis=1).max(axis=1)
    return tr.ewm(com=period - 1, adjust=False).mean()


def vwap(df: pd.DataFrame) -> pd.Series:
    """
    VWAP - Volume Weighted Average Price (intraday, resets each day).
    Expects columns: open, high, low, close, volume, date/timestamp.
    """
    typical_price = (df["high"] + df["low"] + df["close"]) / 3
    cumulative_tp_vol = (typical_price * df["volume"]).cumsum()
    cumulative_vol = df["volume"].cumsum()
    return cumulative_tp_vol / cumulative_vol.replace(0, np.nan)


def bollinger_bands(series: pd.Series, period: int = 20, std_dev: float = 2.0):
    """Bollinger Bands — returns (upper, middle, lower)."""
    middle = sma(series, period)
    std = series.rolling(window=period).std()
    upper = middle + (std * std_dev)
    lower = middle - (std * std_dev)
    return upper, middle, lower


def detect_crossover(fast: pd.Series, slow: pd.Series) -> pd.Series:
    """
    Detect crossover events.
    Returns: +1 (bullish cross — fast > slow and was below), -1 (bearish), 0 (no cross)
    """
    prev_fast = fast.shift(1)
    prev_slow = slow.shift(1)
    bullish = (fast > slow) & (prev_fast <= prev_slow)
    bearish = (fast < slow) & (prev_fast >= prev_slow)
    result = pd.Series(0, index=fast.index)
    result[bullish] = 1
    result[bearish] = -1
    return result


def candles_to_dataframe(candles: list) -> pd.DataFrame:
    """Convert list of OHLCV dicts to DataFrame with proper types."""
    if not candles:
        return pd.DataFrame()
    df = pd.DataFrame(candles)
    df["date"] = pd.to_datetime(df["date"], format="ISO8601", utc=False).dt.tz_localize(None)
    df = df.sort_values("date").reset_index(drop=True)
    for col in ["open", "high", "low", "close"]:
        if col in df.columns:
            df[col] = df[col].astype(float)
    if "volume" in df.columns:
        df["volume"] = df["volume"].astype(float)
    return df


def compute_drawdown(equity_curve: pd.Series) -> float:
    """Maximum drawdown as a percentage."""
    roll_max = equity_curve.cummax()
    drawdown = (equity_curve - roll_max) / roll_max.replace(0, np.nan)
    return float(drawdown.min() * 100) if len(drawdown) > 0 else 0.0
