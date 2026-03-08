import asyncio
from datetime import datetime, timedelta
import pytz
from sqlalchemy import select
from app.database.base import AsyncSessionLocal
from app.database.models import NiftyCandle

async def test_db():
    async with AsyncSessionLocal() as db:
        ist = pytz.timezone("Asia/Kolkata")
        now_ist = datetime.now(ist)
        
        # Get yesterday's date (or last friday if today is monday)
        if now_ist.weekday() == 0:
            yesterday = now_ist - timedelta(days=3)
        else:
            yesterday = now_ist - timedelta(days=1)
            
        yesterday_open = ist.localize(datetime(yesterday.year, yesterday.month, yesterday.day, 9, 0, 0))
        
        stmt = select(NiftyCandle).filter(
            NiftyCandle.symbol == "NIFTY 50",
            NiftyCandle.interval == "1minute",
            NiftyCandle.timestamp >= yesterday_open
        ).order_by(NiftyCandle.timestamp.asc())
        
        result = await db.execute(stmt)
        candles = result.scalars().all()
        
        print(f"Total candles found: {len(candles)}")
        if candles:
            print(f"First candle: {candles[0].timestamp}")
            print(f"Last candle: {candles[-1].timestamp}")

if __name__ == "__main__":
    asyncio.run(test_db())
