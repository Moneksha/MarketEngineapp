import pandas as pd
from app.services.backtest_engine import _fetch_ohlcv, _run_strategy, _simulate_trades
from datetime import datetime, timedelta

from_date = "2016-03-01"
to_date = "2025-01-01"

warmup = "2000-01-01"
df = _fetch_ohlcv("RELIANCE", warmup, to_date)
# FIX TZ
df.index = df.index.tz_localize(None).tz_localize("Asia/Kolkata")

# Keep only market hours
df_ist = df.between_time("09:15", "15:29")

df_ist["trade_date"] = df_ist.index.date

resampled = df_ist.groupby("trade_date").agg({
    "open": "first",
    "high": "max",
    "low": "min",
    "close": "last",
    "volume": "sum",
})

resampled.index = pd.to_datetime(resampled.index)
resampled.index = resampled.index.tz_localize("Asia/Kolkata").tz_convert("UTC")

# EMA
sma = resampled["close"].rolling(window=20, min_periods=20).mean()
seeded = resampled["close"].copy()
idx = seeded.index.get_loc(sma.first_valid_index())
seeded.iloc[:idx] = pd.NA
seeded.iloc[idx] = sma.iloc[idx]
resampled["ema"] = seeded.ewm(span=20, adjust=False).mean()

# sig
resampled["prev_close"] = resampled["close"].shift(1)
resampled["prev_ema"] = resampled["ema"].shift(1)

resampled = resampled[resampled["ema"].notna()]
resampled["signal"] = 0
crossed_above = (resampled["close"] > resampled["ema"]) & (resampled["prev_close"] <= resampled["prev_ema"])
crossed_below = (resampled["close"] < resampled["ema"]) & (resampled["prev_close"] >= resampled["prev_ema"])
resampled.loc[crossed_above, "signal"] = 1   # BUY
resampled.loc[crossed_below, "signal"] = -1  # SELL

resampled["signal_exec"] = resampled["signal"].shift(1).fillna(0)

# Simulate
sig = resampled[resampled.index >= pd.Timestamp(from_date, tz="UTC")]
trades = _simulate_trades(sig)
print(f"Trades: {len(trades)}")

returns = [t["return_pts"] for t in trades]
print(f"Total PnL (points): {sum(returns):.2f}")
