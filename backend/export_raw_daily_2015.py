import pandas as pd
from app.services.backtest_engine import _fetch_ohlcv, _resample

from_date = "2015-01-01"
to_date = "2025-01-01"

print("Fetching and resampling data from 2015...")
# Fetch enough to cover the dates
df_raw = _fetch_ohlcv("RELIANCE", from_date, to_date)
df_daily = _resample(df_raw, "1D")

# Clean up index and output
df_daily["date"] = df_daily.index.strftime("%Y-%m-%d")
cols = ["date", "open", "high", "low", "close", "volume"]
df_daily = df_daily[cols]

try:
    df_daily.to_excel("reliance_daily_data.xlsx", index=False)
    print("Successfully exported to reliance_daily_data.xlsx")
except Exception as e:
    print(f"Excel export failed: {e}. Falling back to CSV.")
    df_daily.to_csv("reliance_daily_data.csv", index=False)
    print("Successfully exported to reliance_daily_data.csv")
