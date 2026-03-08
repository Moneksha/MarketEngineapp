import pandas as pd
from sqlalchemy import create_engine

print("Fetching raw 1-minute data from DB for 2015...")

engine = create_engine("postgresql://postgres:2411@localhost:5432/Equity_db")
query = """
    SELECT date as timestamp, open, high, low, close, volume
    FROM reliance_ohlcv
    WHERE date >= '2015-01-01 00:00:00' AND date <= '2015-12-31 23:59:59'
    ORDER BY date ASC
"""

df_raw = pd.read_sql(query, engine)

try:
    df_raw["timestamp"] = df_raw["timestamp"].dt.tz_localize(None)
    df_raw.to_excel("reliance_1m_data_2015.xlsx", index=False)
    print("Successfully exported to reliance_1m_data_2015.xlsx")
except Exception as e:
    print(f"Excel export failed: {e}. Falling back to CSV.")
    df_raw.to_csv("reliance_1m_data_2015.csv", index=False)
    print("Successfully exported to reliance_1m_data_2015.csv")

