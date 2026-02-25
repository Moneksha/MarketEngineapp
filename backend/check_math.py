import asyncio
import pandas as pd
from loguru import logger
from app.services.kite_service import kite_service
from app.utils.indicators import ema

async def manual_run():
    print("Testing Strategy Data Alignment...")
    # Fetch today's candles manually exactly how runner does it
    try:
        from datetime import datetime
        now = datetime.now()
        start = now.replace(hour=9, minute=15, second=0, microsecond=0)
        
        nifty_quote = await kite_service.get_nifty_quote()
        token = nifty_quote.get("instrument_token", 256265)
        # Fetch 200 minutes
        candles = await kite_service.get_historical(
            instrument_token=token,
            from_date=start,
            to_date=now,
            interval="minute"
        )
        df = pd.DataFrame(candles)
        df["close"] = df["close"].astype(float)
        df["ema21"] = ema(df["close"], 21)
        
        row_now = df.iloc[-1]
        row_prev = df.iloc[-2]
        
        print("\n--- Currently Forming Candle (df.iloc[-1]) ---")
        print(f"Timestamp: {row_now['date']}")
        print(row_now[["close", "ema21"]])
        
        print("\n--- Completed Candle (df.iloc[-2]) ---")
        print(f"Timestamp: {row_prev['date']}")
        print(row_prev[["close", "ema21"]])
        
        # Add latency check
        from datetime import timezone, timedelta
        now_ts = pd.Timestamp.now(tz=row_now['date'].tz)
        latency = (now_ts - row_now['date']).total_seconds()
        print(f"\n=> TIME DIFFERENCE (NOW vs LAST CANDLE): {latency} seconds")
        
        if float(row_prev["close"]) > float(row_prev["ema21"]):
            print("\n=> SIGNAL SHOULD BE: SELL PE (Bullish)")
        else:
            print("\n=> SIGNAL SHOULD BE: SELL CE (Bearish)")

    except Exception as e:
        print(f"Error fetching candles: {e}")

if __name__ == "__main__":
    asyncio.run(manual_run())
