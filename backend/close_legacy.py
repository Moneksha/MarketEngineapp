import asyncio
from sqlalchemy import update
from app.database.base import AsyncSessionLocal
from app.database.models import Trade
from datetime import datetime

async def main():
    async with AsyncSessionLocal() as db:
        stmt = update(Trade).where(Trade.status == "ACTIVE", Trade.strategy_id == "ema_21_option_selling").values(status="CLOSED", pnl=10, exit_price=25731, exit_time=datetime.now())
        await db.execute(stmt)
        await db.commit()
    print("Closed legacy trade.")

if __name__ == "__main__":
    asyncio.run(main())
