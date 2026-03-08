import pandas as pd
from sqlalchemy import create_engine, text

DB_URL = "postgresql://postgres:2411@localhost:5432/Equity_db"
engine = create_engine(DB_URL)

query = text("""
    SELECT date, close, open, high, low, volume
    FROM nifty50_ohlcv
    WHERE date >= '2022-01-04 00:00:00' AND date <= '2022-01-04 23:59:59'
    ORDER BY date ASC
""")

with engine.connect() as conn:
    df = pd.read_sql(query, conn)

df["date"] = pd.to_datetime(df["date"])
if df["date"].dt.tz is not None:
    df["date"] = df["date"].dt.tz_localize(None)

df["date"] = df["date"].dt.tz_localize("Asia/Kolkata")
df = df.set_index("date")

df_ist = df.between_time("09:15", "15:29")

try:
    resampled = df_ist.resample("1h", offset="15min").agg({
        "open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"
    }).dropna()
except TypeError:
    # Older pandas fallback
    resampled = df_ist.resample("1h", base=15).agg({
        "open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"
    }).dropna()

print(resampled)
