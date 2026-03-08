import pandas as pd
from app.services.backtest_engine import _fetch_ohlcv, _resample, _calc_ema, _run_strategy, _simulate_trades
from datetime import datetime, timedelta

from_date = "2016-03-01"
to_date = "2025-01-01"

# test 1: 500 days warmup
warmup1 = (datetime.strptime(from_date, "%Y-%m-%d") - timedelta(days=500)).strftime("%Y-%m-%d")
df1 = _fetch_ohlcv("RELIANCE", warmup1, to_date)
df1 = _resample(df1, "1D")
sig1 = _run_strategy(df1, 20)
sig1 = sig1[sig1.index >= pd.Timestamp(from_date, tz="UTC")]
trades1 = _simulate_trades(sig1)
print(f"Trades with 500d warmup: {len(trades1)}")

# test 2: full history warmup (from 2000)
warmup2 = "2000-01-01"
df2 = _fetch_ohlcv("RELIANCE", warmup2, to_date)
df2 = _resample(df2, "1D")
sig2 = _run_strategy(df2, 20)
sig2 = sig2[sig2.index >= pd.Timestamp(from_date, tz="UTC")]
trades2 = _simulate_trades(sig2)
print(f"Trades with full history warmup: {len(trades2)}")

