import pandas as pd
from app.services.backtest_engine import _fetch_ohlcv, _resample, _calc_ema
from datetime import datetime, timedelta

from_date = "2016-03-01"
to_date = "2025-01-01"
timeframe = "1D"
ema_period = 20

warmup_start = (datetime.strptime(from_date, "%Y-%m-%d") - timedelta(days=500)).strftime("%Y-%m-%d")

print("Fetching data...")
df_raw = _fetch_ohlcv("RELIANCE", warmup_start, to_date)
df = _resample(df_raw, timeframe)

df["ema"] = _calc_ema(df["close"], ema_period)
df["prev_close"] = df["close"].shift(1)
df["prev_ema"] = df["ema"].shift(1)

df["signal"] = 0
mask = df["ema"].notna() & df["prev_ema"].notna()
crossed_above = mask & (df["close"] > df["ema"]) & (df["prev_close"] <= df["prev_ema"])
crossed_below = mask & (df["close"] < df["ema"]) & (df["prev_close"] >= df["prev_ema"])
df.loc[crossed_above, "signal"] = 1
df.loc[crossed_below, "signal"] = -1

df["signal_exec"] = df["signal"].shift(1).fillna(0)

export_df = df[["open", "high", "low", "close", "ema", "signal", "signal_exec"]].copy()

export_df["executed_price"] = None
exec_mask = export_df["signal_exec"] != 0
export_df.loc[exec_mask, "executed_price"] = export_df.loc[exec_mask, "open"]

export_df["trade_direction_opened"] = None
export_df.loc[export_df["signal_exec"] == 1, "trade_direction_opened"] = "LONG (Entry) / SHORT (Exit)"
export_df.loc[export_df["signal_exec"] == -1, "trade_direction_opened"] = "SHORT (Entry) / LONG (Exit)"

export_df["date_str"] = export_df.index.strftime("%Y-%m-%d")

cols = ["date_str", "open", "high", "low", "close", "ema", "signal", "signal_exec", "executed_price", "trade_direction_opened"]
export_df = export_df[cols]

try:
    export_df.to_excel("reliance_backtest_verification.xlsx", index=False)
    print("Saved to reliance_backtest_verification.xlsx")
except ImportError:
    print("openpyxl not found, saving to csv instead.")
    export_df.to_csv("reliance_backtest_verification.csv", index=False)
    print("Saved to reliance_backtest_verification.csv")

print("Done.")
