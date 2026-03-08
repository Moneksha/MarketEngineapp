import pandas as pd
from app.services.backtest_engine import _fetch_ohlcv

df = _fetch_ohlcv("RELIANCE", "2020-03-10", "2020-03-12")
print("Raw data head:")
print(df.head())

df_ist = df.copy()
df_ist.index = df_ist.index.tz_convert("Asia/Kolkata")
print("IST data head:")
print(df_ist.head())

filtered = df_ist.between_time("09:15", "15:30")
print("Filtered data head:")
print(filtered.head())
print("Filtered data tail:")
print(filtered.tail())

