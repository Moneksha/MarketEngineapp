import asyncio
from datetime import datetime
from sqlalchemy import select
from app.database.base import AsyncSessionLocal
from app.database.models import StrategyRun

async def main():
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(StrategyRun)
            .where(StrategyRun.strategy_id == "ema_21_option_selling")
            .order_by(StrategyRun.run_at.desc())
            .limit(20)
        )
        runs = result.scalars().all()
        runs.reverse()
        from zoneinfo import ZoneInfo
        ist = ZoneInfo('Asia/Kolkata')
        print("Last 20 Strategy Runs (Oldest to Newest):")
        for r in runs:
            ist_time = r.run_at.astimezone(ist) if r.run_at else None
            time_str = ist_time.strftime('%H:%M:%S') if ist_time else "None"
            print(f"Time: {time_str} | Signal: {r.signal} | Price: {r.price} | Data: {r.candle_data}")

if __name__ == "__main__":
    asyncio.run(main())
