"""
ingest_nifty50_feather.py
-------------------------
Ingests NIFTY 50 1-minute OHLCV data from a Feather file into PostgreSQL.

Usage:
    python scripts/ingest_nifty50_feather.py

The script will:
1. Create the database Equity_db if it does not exist.
2. Create the table nifty50_ohlcv if it does not exist.
3. Load the feather file and insert all rows (handles duplicates with ON CONFLICT DO NOTHING).
"""

import pandas as pd
import psycopg2
from psycopg2 import sql
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from sqlalchemy import create_engine, text
import time
import os

# ── Config ────────────────────────────────────────────────────────────────────
FEATHER_PATH = "/Users/dmoneksh/Desktop/2026 data and codes/NIFTY50_1minute_2000-01-01_to_2026-03-06.feather"

DB_USER = "postgres"
DB_PASS = "2411"
DB_HOST = "localhost"
DB_PORT = "5432"
DB_NAME = "Equity_db"

ADMIN_URL = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/postgres"
DB_URL = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

TABLE_NAME = "nifty50_ohlcv"
CHUNK_SIZE = 10_000  # rows per insert batch

# ── Step 1: Create DB if not exists ──────────────────────────────────────────
def ensure_database_exists():
    print(f"[1/4] Ensuring database '{DB_NAME}' exists...")
    conn = psycopg2.connect(ADMIN_URL)
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (DB_NAME,))
    if not cur.fetchone():
        cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(DB_NAME)))
        print(f"  ✅ Created database '{DB_NAME}'")
    else:
        print(f"  ℹ️  Database '{DB_NAME}' already exists")
    cur.close()
    conn.close()

# ── Step 2: Create table ─────────────────────────────────────────────────────
def ensure_table_exists(engine):
    print(f"[2/4] Ensuring table '{TABLE_NAME}' exists...")
    create_sql = f"""
    CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
        date        TIMESTAMP WITH TIME ZONE NOT NULL,
        open        DOUBLE PRECISION,
        high        DOUBLE PRECISION,
        low         DOUBLE PRECISION,
        close       DOUBLE PRECISION,
        volume      DOUBLE PRECISION,
        PRIMARY KEY (date)
    );
    CREATE INDEX IF NOT EXISTS idx_nifty50_ohlcv_date ON {TABLE_NAME} (date);
    """
    with engine.connect() as conn:
        conn.execute(text(create_sql))
        conn.commit()
    print(f"  ✅ Table '{TABLE_NAME}' ready")

# ── Step 3: Load Feather file ─────────────────────────────────────────────────
def load_feather():
    print(f"[3/4] Loading Feather file...")
    if not os.path.exists(FEATHER_PATH):
         raise FileNotFoundError(f"Feather file not found at: {FEATHER_PATH}")
    
    df = pd.read_feather(FEATHER_PATH)
    print(f"  ℹ️  Loaded {len(df):,} rows. Columns: {list(df.columns)}")

    # Normalize column names to lowercase
    df.columns = [c.lower().strip() for c in df.columns]

    # Detect and parse the date/timestamp column
    date_col = None
    for c in ["date", "datetime", "timestamp", "time"]:
        if c in df.columns:
            date_col = c
            break

    if date_col is None:
        # If index is a DatetimeIndex, reset it
        if isinstance(df.index, pd.DatetimeIndex):
            df = df.reset_index()
            df.rename(columns={df.columns[0]: "date"}, inplace=True)
            date_col = "date"
        else:
            raise ValueError(f"Cannot find date column. Columns are: {list(df.columns)}")

    if date_col != "date":
        df.rename(columns={date_col: "date"}, inplace=True)

    # Convert to datetime, handle tz
    df["date"] = pd.to_datetime(df["date"], utc=True)
    df = df.sort_values("date").reset_index(drop=True)

    # Keep only required columns
    required_cols = ["date", "open", "high", "low", "close", "volume"]
    df = df[[c for c in required_cols if c in df.columns]]

    print(f"  ✅ Data range: {df['date'].min()} → {df['date'].max()}")
    return df

# ── Step 4: Insert into PostgreSQL ────────────────────────────────────────────
def insert_data(df, engine):
    print(f"[4/4] Inserting {len(df):,} rows into '{TABLE_NAME}'...")
    start = time.time()

    # Use raw psycopg2 COPY for maximum speed via temp table + ON CONFLICT
    total_chunks = (len(df) + CHUNK_SIZE - 1) // CHUNK_SIZE
    rows_inserted = 0

    for i in range(0, len(df), CHUNK_SIZE):
        chunk = df.iloc[i : i + CHUNK_SIZE]
        chunk_num = i // CHUNK_SIZE + 1

        # Use pandas to_sql with method='multi' and handle conflicts via a temp table
        chunk.to_sql(
            "__nifty50_temp",
            engine,
            if_exists="replace",
            index=False,
            method="multi",
        )

        with engine.connect() as conn:
            conn.execute(text(f"""
                INSERT INTO {TABLE_NAME} (date, open, high, low, close, volume)
                SELECT date, open, high, low, close, volume
                FROM __nifty50_temp
                ON CONFLICT (date) DO NOTHING
            """))
            conn.execute(text("DROP TABLE IF EXISTS __nifty50_temp"))
            conn.commit()

        rows_inserted += len(chunk)
        elapsed = time.time() - start
        
        # Only print every 10 chunks to avoid spamming the console too much for huge files
        if chunk_num % 10 == 0 or chunk_num == total_chunks:
             print(f"  [{chunk_num}/{total_chunks}] Inserted {rows_inserted:,} rows ({elapsed:.1f}s)")

    elapsed = time.time() - start
    print(f"\n  ✅ Done! {rows_inserted:,} rows processed in {elapsed:.1f}s")

# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("  NIFTY 50 OHLCV Feather → PostgreSQL Ingestion")
    print("=" * 60)

    ensure_database_exists()

    engine = create_engine(DB_URL, echo=False)
    ensure_table_exists(engine)

    df = load_feather()
    insert_data(df, engine)

    # Final verification
    with engine.connect() as conn:
        result = conn.execute(text(f"SELECT COUNT(*), MIN(date), MAX(date) FROM {TABLE_NAME}"))
        count, min_date, max_date = result.fetchone()
        print(f"\n✅ Verification: {count:,} rows in DB | {min_date} → {max_date}")

    print("=" * 60)
    print("  Ingestion Complete!")
    print("=" * 60)
