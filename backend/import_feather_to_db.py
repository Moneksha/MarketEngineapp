#!/usr/bin/env python3
"""
import_feather_to_db.py
-----------------------
Import equity OHLCV data from Feather files into the `equity_prices` PostgreSQL
table inside MarketEngine_db.

Usage:
    python import_feather_to_db.py /path/to/feather/directory

    # Or use the FEATHER_DATA_DIR env variable:
    FEATHER_DATA_DIR=/path/to/feather python import_feather_to_db.py
"""

from __future__ import annotations

import os
import sys
import time
from io import StringIO

import pandas as pd
from sqlalchemy import create_engine, text

# ── Configuration ──────────────────────────────────────────────────────────────
DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:2411@localhost:5432/MarketEngine_db",
)

BATCH_SIZE = 50_000  # rows per COPY batch


def get_feather_dir() -> str:
    """Resolve the directory containing Feather files."""
    if len(sys.argv) > 1:
        return sys.argv[1]
    return os.getenv("FEATHER_DATA_DIR", "")


def discover_files(directory: str) -> list[tuple[str, str]]:
    """Return [(symbol, filepath), ...] for all Feather files."""
    files = []
    for filename in sorted(os.listdir(directory)):
        if filename.endswith(".feather"):
            symbol = filename.split("_1minute")[0].upper()
            files.append((symbol, os.path.join(directory, filename)))
    return files


def import_symbol(engine, symbol: str, filepath: str) -> int:
    """Import a single Feather file into equity_prices. Returns row count."""
    print(f"  📂 Reading {os.path.basename(filepath)} ...")
    df = pd.read_feather(filepath)

    # Normalize column names
    if "timestamp" in df.columns:
        df = df.rename(columns={"timestamp": "date"})

    df["date"] = pd.to_datetime(df["date"])

    # Strip timezone if present (store as naive local IST)
    if df["date"].dt.tz is not None:
        df["date"] = df["date"].dt.tz_localize(None)

    # Build the insert dataframe
    insert_df = pd.DataFrame({
        "symbol": symbol,
        "datetime": df["date"],
        "open": df["open"].round(2),
        "high": df["high"].round(2),
        "low": df["low"].round(2),
        "close": df["close"].round(2),
        "volume": df["volume"].astype(int),
    })

    # Drop any rows with NaN in critical columns
    insert_df = insert_df.dropna(subset=["datetime", "close"])

    total_rows = len(insert_df)
    if total_rows == 0:
        print(f"  ⚠️  No valid rows in {os.path.basename(filepath)}")
        return 0

    # Use raw psycopg2 COPY for maximum speed
    raw_conn = engine.raw_connection()
    cursor = raw_conn.cursor()

    try:
        # Process in batches
        inserted = 0
        for start in range(0, total_rows, BATCH_SIZE):
            batch = insert_df.iloc[start : start + BATCH_SIZE]

            # Create a temp table, COPY into it, then INSERT with ON CONFLICT
            cursor.execute("""
                CREATE TEMP TABLE _tmp_equity (LIKE equity_prices INCLUDING DEFAULTS)
                ON COMMIT DROP
            """)

            # Write batch to CSV buffer
            buf = StringIO()
            batch.to_csv(buf, index=False, header=False, sep="\t", na_rep="\\N")
            buf.seek(0)

            cursor.copy_from(
                buf,
                "_tmp_equity",
                columns=["symbol", "datetime", "open", "high", "low", "close", "volume"],
                sep="\t",
                null="\\N",
            )

            cursor.execute("""
                INSERT INTO equity_prices (symbol, datetime, open, high, low, close, volume)
                SELECT symbol, datetime, open, high, low, close, volume
                FROM _tmp_equity
                ON CONFLICT (symbol, datetime) DO NOTHING
            """)

            raw_conn.commit()
            inserted += len(batch)
            print(f"    ✅ {inserted:,} / {total_rows:,} rows", end="\r")

        print()  # newline after progress
        return total_rows

    except Exception as e:
        raw_conn.rollback()
        print(f"  ❌ Error importing {symbol}: {e}")
        return 0
    finally:
        cursor.close()
        raw_conn.close()


def main():
    feather_dir = get_feather_dir()
    if not feather_dir or not os.path.isdir(feather_dir):
        print("❌ Please provide a valid Feather directory.")
        print(f"   Usage: python {sys.argv[0]} /path/to/feather/dir")
        print(f"   Or set FEATHER_DATA_DIR environment variable.")
        sys.exit(1)

    files = discover_files(feather_dir)
    if not files:
        print(f"❌ No .feather files found in {feather_dir}")
        sys.exit(1)

    print(f"🔄 Found {len(files)} Feather files in: {feather_dir}")
    print(f"📡 Target database: {DB_URL.split('@')[1] if '@' in DB_URL else DB_URL}")
    print()

    engine = create_engine(DB_URL, echo=False)

    # Verify the table exists
    with engine.connect() as conn:
        result = conn.execute(text(
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'equity_prices'"
        ))
        if result.scalar() == 0:
            print("❌ Table 'equity_prices' does not exist. Run Alembic migrations first.")
            print("   cd backend && ./venv/bin/alembic upgrade head")
            sys.exit(1)

    total_imported = 0
    start_time = time.time()

    for i, (symbol, filepath) in enumerate(files, 1):
        print(f"\n[{i}/{len(files)}] Importing {symbol} ...")
        count = import_symbol(engine, symbol, filepath)
        total_imported += count
        print(f"  → {count:,} rows imported for {symbol}")

    elapsed = time.time() - start_time
    print(f"\n{'='*60}")
    print(f"✅ Import complete!")
    print(f"   Total rows: {total_imported:,}")
    print(f"   Time taken: {elapsed:.1f}s")
    print(f"{'='*60}")

    # Summary query
    with engine.connect() as conn:
        result = conn.execute(text(
            "SELECT symbol, COUNT(*), MIN(datetime)::text, MAX(datetime)::text "
            "FROM equity_prices GROUP BY symbol ORDER BY symbol"
        ))
        print(f"\n📊 Database summary:")
        for row in result:
            print(f"   {row[0]:>15s}: {row[1]:>10,} rows  ({row[2]} → {row[3]})")


if __name__ == "__main__":
    main()
