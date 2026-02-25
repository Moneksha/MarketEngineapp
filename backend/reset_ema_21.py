import asyncio
from sqlalchemy import delete
from app.database.base import AsyncSessionLocal
from app.database.models import Trade, PnLSnapshot, StrategyRun

async def main():
    async with AsyncSessionLocal() as db:
        await db.execute(delete(Trade).where(Trade.strategy_id == "ema_21_option_selling"))
        await db.execute(delete(PnLSnapshot).where(PnLSnapshot.strategy_id == "ema_21_option_selling"))
        await db.execute(delete(StrategyRun).where(StrategyRun.strategy_id == "ema_21_option_selling"))
        await db.commit()
    print("Reset complete. All trades, PnL snapshots, and runs for 'ema_21_option_selling' have been deleted from the database.")

if __name__ == "__main__":
    asyncio.run(main())
