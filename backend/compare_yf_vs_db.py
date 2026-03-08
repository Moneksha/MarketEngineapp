"""
Compare Yahoo Finance daily OHLCV for RELIANCE.NS vs our local DB data.
Runs a side-by-side diff and shows mismatches.
"""
import yfinance as yf
import pandas as pd
from sqlalchemy import create_engine, text

DB_URL = "postgresql://postgres:2411@localhost:5432/Equity_db"
engine = create_engine(DB_URL)

# --- Fetch from Yahoo Finance ---
tkr = yf.Ticker("RELIANCE.NS")
yf_df = tkr.history(start="2024-06-01", end="2024-11-01")
yf_df.index = yf_df.index.tz_convert("Asia/Kolkata")
yf_df.index = yf_df.index.normalize()  # Strip time, keep date

# Keep only OHLCV columns
yf_df = yf_df[["Open", "Close", "High", "Low", "Volume"]].copy()
yf_df.columns = ["yf_open", "yf_close", "yf_high", "yf_low", "yf_volume"]
yf_df = yf_df.round(2)

# --- Fetch from our DB (1-min data, resample to daily) ---
with engine.connect() as conn:
    db_raw = pd.read_sql(
        text("""
            SELECT date, open, high, low, close, volume 
            FROM reliance_ohlcv 
            WHERE date >= '2024-05-28T00:00:00+00:00' 
              AND date <= '2024-10-31T23:59:59+00:00'
            ORDER BY date ASC
        """),
        conn
    )

db_raw["date"] = pd.to_datetime(db_raw["date"], utc=True).dt.tz_convert("Asia/Kolkata")
db_raw = db_raw.set_index("date")
db_raw = db_raw.between_time("09:15", "15:30")

# Keep only market hours then resample to daily OHLCV
db_raw["trade_date"] = db_raw.index.normalize()
db_daily = db_raw.groupby("trade_date").agg(
    db_open=("open", "first"),
    db_high=("high", "max"),
    db_low=("low", "min"),
    db_close=("close", "last"),
    db_volume=("volume", "sum"),
)
db_daily = db_daily.round(2)
db_daily.index = db_daily.index.tz_localize(None)

yf_df.index = yf_df.index.tz_localize(None)

# --- Merge side by side ---
merged = yf_df.join(db_daily, how="inner")
merged["open_diff"] = (merged["yf_open"] - merged["db_open"]).round(2)
merged["close_diff"] = (merged["yf_close"] - merged["db_close"]).round(2)

print("=== RELIANCE: Yahoo Finance vs Database Daily OHLCV ===")
print(f"{'Date':<14} {'YF_Open':>10} {'DB_Open':>10} {'ΔOpen':>8}  {'YF_Close':>10} {'DB_Close':>10} {'ΔClose':>8}")
print("-" * 80)
for date, row in merged.iterrows():
    flag_open  = " ⚠" if abs(row.open_diff)  > 1.0 else ""
    flag_close = " ⚠" if abs(row.close_diff) > 1.0 else ""
    print(f"{str(date.date()):<14} {row.yf_open:>10.2f} {row.db_open:>10.2f} {row.open_diff:>8.2f}{flag_open}  "
          f"{row.yf_close:>10.2f} {row.db_close:>10.2f} {row.close_diff:>8.2f}{flag_close}")
