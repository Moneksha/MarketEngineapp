from sqlalchemy import create_engine, text
import pandas as pd

DB_URL = "postgresql://postgres:2411@localhost:5432/Equity_db"
engine = create_engine(DB_URL)

query = text("""
    SELECT date, close
    FROM reliance_ohlcv
    WHERE date >= '2022-01-04 00:00:00' AND date <= '2022-01-04 23:59:59'
    ORDER BY date ASC
    LIMIT 20;
""")

with engine.connect() as conn:
    df = pd.read_sql(query, conn)

print("First 20 raw DB rows for 2022-01-04:")
print(df)
