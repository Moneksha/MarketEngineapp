import pandas as pd
from app.services.backtest_engine import _fetch_ohlcv, _resample, _calc_ema, _run_strategy, _simulate_trades

warmup = "2000-01-01"
# We fetch a few days to see the exact time bounds
df = _fetch_ohlcv("RELIANCE", "2020-03-10", "2020-03-12")
df_ist = df.copy()
df_ist.index = df_ist.index.tz_convert("Asia/Kolkata")
print("Unique times at end of day:")
print(df_ist.index.time[-50:])

