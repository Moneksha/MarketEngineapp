"""
backtest_engine.py
------------------
EMA crossover backtesting engine for equity research dashboard.
Fetches OHLCV data from the equity_prices table in MarketEngine_db,
applies modular strategies, and computes metrics.
"""

from __future__ import annotations

import math
import os
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text

# ── DB Config (uses the same MarketEngine_db as the rest of the app) ──────────
_SYNC_DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:2411@localhost:5432/MarketEngine_db",
).replace("+asyncpg", "")

_engine = create_engine(_SYNC_DB_URL, echo=False, pool_pre_ping=True)

# ── Timeframe mapping ─────────────────────────────────────────────────────────
TIMEFRAME_MAP = {
    "1m": "1min",
    "5m": "5min",
    "15m": "15min",
    "1h": "1h",
    "1D": "1D",
    "1W": "1W",
}


def _fetch_ohlcv(symbol: str, from_date: str, to_date: str) -> pd.DataFrame:
    """Fetch 1-minute OHLCV data from the equity_prices table."""
    symbol_upper = symbol.upper()

    query = text("""
        SELECT datetime AS date, open, high, low, close, volume
        FROM equity_prices
        WHERE symbol = :symbol
          AND datetime >= :from_date
          AND datetime <= :to_date
        ORDER BY datetime ASC
    """)

    with _engine.connect() as conn:
        df = pd.read_sql(query, conn, params={
            "symbol": symbol_upper,
            "from_date": from_date + " 00:00:00",
            "to_date": to_date + " 23:59:59",
        })

    if df.empty:
        return pd.DataFrame()

    df["date"] = pd.to_datetime(df["date"])

    # Database stores naive IST timestamps — localize and convert to UTC
    if df["date"].dt.tz is not None:
        df["date"] = df["date"].dt.tz_localize(None)

    df["date"] = df["date"].dt.tz_localize("Asia/Kolkata").dt.tz_convert("UTC")
    df = df.set_index("date").sort_index()
    return df

import re

def _parse_timeframe(timeframe: str) -> str:
    """
    Parses a string like '7m', '2h', '1D' into a pd.Timedelta/Offset alias.
    m -> min
    h -> h
    D -> D
    W -> W-FRI
    M -> ME
    """
    if timeframe == '1W': return '1W-FRI'
    if timeframe == '1M': return '1ME'
    
    match = re.match(r'^(\d+)([mhDWM])$', timeframe)
    if not match:
        return timeframe # Fallback or default
    
    val, unit = match.groups()
    if unit == 'm':
        return f"{val}min"
    elif unit == 'h':
        return f"{val}h"
    elif unit == 'D':
        return f"{val}D"
    elif unit == 'W':
        return f"{val}W-FRI"
    elif unit == 'M':
        return f"{val}ME"
    return timeframe

def _resample(df: pd.DataFrame, timeframe: str) -> pd.DataFrame:

    # Ensure data is timezone-aware and converted to Asia/Kolkata properly
    df_ist = df.copy()
    if df_ist.index.tz is None:
        df_ist.index = df_ist.index.tz_localize("Asia/Kolkata")
    else:
        df_ist.index = df_ist.index.tz_convert("Asia/Kolkata")

    # Keep only market hours
    # The user requires Close to be the last trade BEFORE 15:30 IST.
    # Therefore, we filter up to 15:29.
    df_ist = df_ist.between_time("09:15", "15:29")
    
    tf = _parse_timeframe(timeframe)

    if tf == "1min":
        df_ist.index = df_ist.index.tz_convert("UTC")
        return df_ist

    # Resample based on the timeframe requested
    if tf.endswith("D") or tf.endswith("W-FRI") or tf.endswith("ME"):
        if tf.endswith("W-FRI") or tf.endswith("ME"):
             resampled = df_ist.resample(tf).agg({
                "open": "first",
                "high": "max",
                "low": "min",
                "close": "last",
                "volume": "sum",
            }).dropna()
             # To keep the date at market close:
             resampled.index = resampled.index.normalize() + pd.Timedelta(hours=15, minutes=29)
        else:
             df_ist["trade_date"] = df_ist.index.date
             
             # Extract the N from ND
             try:
                 n_days = int(tf.replace("D", ""))
             except ValueError:
                 n_days = 1
                 
             if n_days == 1:
                 # Standard daily
                 resampled = df_ist.groupby("trade_date").agg({
                     "open": "first",
                     "high": "max",
                     "low": "min",
                     "close": "last",
                     "volume": "sum",
                 })
                 resampled.index = pd.to_datetime(resampled.index) + pd.Timedelta(hours=15, minutes=29)
             else:
                  # For > 1D like 2D, 3D, group by using standard resample
                  resampled = df_ist.resample(tf).agg({
                     "open": "first",
                     "high": "max",
                     "low": "min",
                     "close": "last",
                     "volume": "sum",
                 }).dropna()
                  resampled.index = resampled.index.normalize() + pd.Timedelta(hours=15, minutes=29)
    else:
        # Intraday resampling (5min, 15min, 1h, etc.)
        try:
            # We use an offset to align the candles to market open (09:15)
            # 9 hours + 15 mins = 555 mins. 
            # In pandas, offset is applied to Midnight.
            resampled = df_ist.resample(tf, offset="15min").agg({
                "open": "first",
                "high": "max",
                "low": "min",
                "close": "last",
                "volume": "sum",
            }).dropna()
        except TypeError:
            # Fallback for older pandas versions
            resampled = df_ist.resample(tf, base=15).agg({
                "open": "first",
                "high": "max",
                "low": "min",
                "close": "last",
                "volume": "sum",
            }).dropna()

    # Convert output back to UTC uniformly for engine calculations
    resampled.index = pd.DatetimeIndex(resampled.index)
    if resampled.index.tz is None:
        resampled.index = resampled.index.tz_localize("Asia/Kolkata")
    resampled.index = resampled.index.tz_convert("UTC")

    return resampled


from .backtest_strategies.registry import get_strategy

def _simulate_trades(df: pd.DataFrame) -> list[dict]:
    """
    Always-in-market EMA crossover simulation.

    Rules:
    - Cross above EMA  → Signal to go LONG at next open
    - Cross below EMA  → Signal to go SHORT at next open
    - At end of data   → close any open position at the last close price
    """
    import pytz
    IST = pytz.timezone("Asia/Kolkata")

    def _ts_ist(ts):
        """Convert a UTC-aware timestamp to IST datetime string (YYYY-MM-DD HH:MM)."""
        import pytz
        IST = pytz.timezone("Asia/Kolkata")
        return ts.astimezone(IST).strftime("%Y-%m-%d %H:%M")

    trades = []
    position = None       # None | 'LONG' | 'SHORT'
    entry_time = None
    entry_price = None

    rows = list(df.iterrows())

    for idx, (ts, row) in enumerate(rows):
        signal_exec = row["signal_exec"]

        if signal_exec == 0:
            continue

        if signal_exec == 1 and position != 'LONG':  # cross above → open LONG
            # Close any existing SHORT position first
            if position == 'SHORT':
                ret_pts = float(entry_price - row["open"])
                ret_pct = float(ret_pts / entry_price * 100)
                duration_min = float((ts - entry_time).total_seconds() / 60)
                trades.append({
                    "entry_time": _ts_ist(entry_time),
                    "exit_time": _ts_ist(ts),
                    "entry_price": round(float(entry_price), 2),
                    "exit_price": round(float(row["open"]), 2),
                    "return_pct": round(ret_pct, 2),
                    "return_pts": round(ret_pts, 2),
                    "duration_minutes": duration_min,
                    "direction": "SHORT",
                    "is_win": bool(ret_pct > 0),
                })

            # Open LONG
            position = 'LONG'
            entry_time = ts
            entry_price = row["open"]

        elif signal_exec == -1 and position != 'SHORT':  # cross below → open SHORT
            # Close any existing LONG position first
            if position == 'LONG':
                ret_pts = float(row["open"] - entry_price)
                ret_pct = float(ret_pts / entry_price * 100)
                duration_min = float((ts - entry_time).total_seconds() / 60)
                trades.append({
                    "entry_time": _ts_ist(entry_time),
                    "exit_time": _ts_ist(ts),
                    "entry_price": round(float(entry_price), 2),
                    "exit_price": round(float(row["open"]), 2),
                    "return_pct": round(ret_pct, 2),
                    "return_pts": round(ret_pts, 2),
                    "duration_minutes": duration_min,
                    "direction": "LONG",
                    "is_win": bool(ret_pct > 0),
                })

            # Open SHORT
            position = 'SHORT'
            entry_time = ts
            entry_price = row["open"]

    # ── Close any open position at the last bar ────────────────────────────────
    if position is not None and entry_time is not None:
        last_ts, last_row = rows[-1]
        
        # If we had a pending signal at the very last bar, we can't execute it
        # Just close out whatever position we are currently holding at the close.
        if position == 'LONG':
            ret_pts = float(last_row["close"] - entry_price)
            ret_pct = float(ret_pts / entry_price * 100)
        else:  # SHORT
            ret_pts = float(entry_price - last_row["close"])
            ret_pct = float(ret_pts / entry_price * 100)

        duration_min = float((last_ts - entry_time).total_seconds() / 60)
        trades.append({
            "entry_time": _ts_ist(entry_time),
            "exit_time": _ts_ist(last_ts),
            "entry_price": round(float(entry_price), 2),
            "exit_price": round(float(last_row["close"]), 2),
            "return_pct": round(ret_pct, 2),
            "return_pts": round(ret_pts, 2),
            "duration_minutes": duration_min,
            "direction": position,
            "is_win": bool(ret_pct > 0),
        })

    return trades



def _build_equity_curve(df: pd.DataFrame, trades: list[dict]) -> list[dict]:
    """Build cumulative PnL (points) and drawdown (points) curves."""
    equity_curve = []

    import pytz
    IST = pytz.timezone("Asia/Kolkata")

    # Build lookup: exit_time → sum of return_pts
    from collections import defaultdict
    pts_lookup = defaultdict(float)
    for t in trades:
        pts_lookup[t["exit_time"]] += t["return_pts"]

    cumulative_pts = 0.0
    peak_pts = 0.0

    for ts, row in df.iterrows():
        ts_ist_key = ts.astimezone(IST).strftime("%Y-%m-%d %H:%M")
        if ts_ist_key in pts_lookup:
            cumulative_pts += pts_lookup[ts_ist_key]
            if cumulative_pts > peak_pts:
                peak_pts = cumulative_pts

        drawdown_pts = cumulative_pts - peak_pts  # always <= 0

        equity_curve.append({
            "date": ts_ist_key,
            "cumulative_pts": round(cumulative_pts, 2),
            "drawdown_pts": round(drawdown_pts, 2),
        })

    return equity_curve



def _compute_metrics(trades: list[dict], equity_curve: list[dict]) -> dict:
    if not trades:
        return {
            "total_return": 0, "total_return_pts": 0, "win_rate": 0, "loss_rate": 0, "sharpe": 0,
            "max_drawdown": 0, "max_drawdown_pts": 0, "total_trades": 0, "profit_factor": 0,
            "avg_win": 0, "avg_loss": 0, "largest_win": 0, "largest_loss": 0,
            "avg_win_pts": 0, "avg_loss_pts": 0, "winners_count": 0, "losers_count": 0,
            "max_win_pts": 0, "max_loss_pts": 0, "avg_win_loss_ratio": 0,
            "total_win_pts": 0, "total_loss_pts": 0, "long_trades_count": 0, "short_trades_count": 0
        }

    returns = [t["return_pct"] for t in trades]
    returns_pts = [t["return_pts"] for t in trades]
    
    wins = [r for r in returns if r > 0]
    losses = [r for r in returns if r <= 0]
    
    wins_pts = [r for r in returns_pts if r > 0]
    losses_pts = [r for r in returns_pts if r <= 0]

    total_return = round(sum(returns), 4)  # simple sum of % returns
    total_return_pts = round(sum(returns_pts), 2)
    win_rate = round((len(wins) / len(returns)) * 100, 2) if returns else 0
    loss_rate = round((len(losses) / len(returns)) * 100, 2) if returns else 0

    # Sharpe (annualised, risk-free = 0) — derived from per-trade % returns
    if len(returns) > 1:
        ret_series = pd.Series(returns)
        mean_ret = ret_series.mean()
        std_ret = ret_series.std()
        sharpe = round((mean_ret / std_ret) * math.sqrt(252), 4) if std_ret > 0 else 0
    else:
        sharpe = 0

    max_drawdown = round(min([c["drawdown_pts"] for c in equity_curve]) if equity_curve else 0, 2)

    # Max drawdown in points (approximate using cumulative returns series)
    cumulative_pts = 0
    peak_pts = 0
    max_dd_pts = 0
    for pts in returns_pts:
        cumulative_pts += pts
        if cumulative_pts > peak_pts:
            peak_pts = cumulative_pts
        dd_pts = cumulative_pts - peak_pts
        if dd_pts < max_dd_pts:
            max_dd_pts = dd_pts
    max_drawdown_pts = round(max_dd_pts, 2)

    gross_profit = sum(wins) if wins else 0
    gross_loss = abs(sum(losses)) if losses else 0
    profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else 9999.0

    avg_win = round(sum(wins) / len(wins), 2) if wins else 0
    avg_loss = round(sum(losses) / len(losses), 2) if losses else 0
    avg_win_pts = round(sum(wins_pts) / len(wins_pts), 2) if wins_pts else 0
    avg_loss_pts = round(sum(losses_pts) / len(losses_pts), 2) if losses_pts else 0
    
    avg_win_loss_ratio = round(abs(avg_win_pts / avg_loss_pts), 2) if avg_loss_pts != 0 else 9999.0
    
    largest_win = round(max(wins), 2) if wins else 0
    largest_loss = round(min(losses), 2) if losses else 0
    
    max_win_pts = round(max(wins_pts), 2) if wins_pts else 0
    max_loss_pts = round(min(losses_pts), 2) if losses_pts else 0

    return {
        "total_return": total_return,
        "total_return_pts": total_return_pts,
        "win_rate": win_rate,
        "loss_rate": loss_rate,
        "sharpe": sharpe,
        "max_drawdown": max_drawdown,
        "max_drawdown_pts": max_drawdown_pts,
        "total_trades": len(trades),
        "profit_factor": profit_factor,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "avg_win_pts": avg_win_pts,
        "avg_loss_pts": avg_loss_pts,
        "largest_win": largest_win,
        "largest_loss": largest_loss,
        "winners_count": len(wins),
        "losers_count": len(losses),
        "max_win_pts": max_win_pts,
        "max_loss_pts": max_loss_pts,
        "avg_win_loss_ratio": avg_win_loss_ratio,
        "total_win_pts": round(sum(wins_pts), 2) if wins_pts else 0,
        "total_loss_pts": round(sum(losses_pts), 2) if losses_pts else 0,
        "long_trades_count": len([t for t in trades if t["direction"] == "LONG"]),
        "short_trades_count": len([t for t in trades if t["direction"] == "SHORT"]),
    }


def run_backtest(
    symbol: str,
    from_date: str,
    to_date: str,
    timeframe: str,
    strategy_id: str = "ema_trend",
    strategy_params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Main entry point: fetch data, load strategy, run simulation, compute metrics.
    """
    params = strategy_params or {}
    
    # Fetch extra warmup bars before from_date.
    warmup_start = "2000-01-01"

    # Fetch raw data
    df_raw = _fetch_ohlcv(symbol, warmup_start, to_date)
    if df_raw.empty:
        return {"error": "No data found for the given parameters."}

    # Resample
    df = _resample(df_raw, timeframe)
    
    # Load and execute modular strategy
    try:
        strategy = get_strategy(strategy_id)
        df_sig = strategy.generate_signals(df, params)
    except Exception as e:
        return {"error": f"Strategy Execution Failed: {str(e)}"}

    if df_sig.empty or "signal" not in df_sig.columns:
        return {"error": "Strategy failed to generate signals or data index too short."}

    # Signal alignment for execution (Next Candle Open)
    df_sig["signal_exec"] = df_sig["signal"].shift(1).fillna(0)

    # Filter to only contain target timeframe (removing warmup bars)
    df_sig = df_sig[df_sig.index >= pd.Timestamp(from_date, tz="UTC")]

    # Simulate trades
    trades = _simulate_trades(df_sig)

    # Build time-series data for charts
    equity_curve = _build_equity_curve(df_sig, trades)

    # Compute performance metrics
    metrics = _compute_metrics(trades, equity_curve)

    return {
        "symbol": symbol,
        "strategy": strategy_id.replace("_", " ").title(),
        "params": params,
        "timeframe": timeframe,
        "from_date": from_date,
        "to_date": to_date,
        "data_points": len(df_sig),
        **metrics,
        "equity_curve": equity_curve,
        "trades": trades,
    }


def get_available_symbols() -> list[dict]:
    """Return all symbols that have data in the equity_prices table."""
    query = text("SELECT DISTINCT symbol FROM equity_prices ORDER BY symbol")
    with _engine.connect() as conn:
        result = conn.execute(query)
        symbols = [row[0] for row in result]
    return [{"symbol": s, "name": s} for s in symbols]
