import asyncio
from sqlalchemy import select
from app.database.base import AsyncSessionLocal
from app.database.models import Trade

async def main():
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Trade)
            .where(Trade.strategy_id == "ema_21_option_selling")
            .order_by(Trade.entry_time.desc())
            .limit(10)
        )
        trades = result.scalars().all()
        for t in trades:
            status = t.status
            entry_t = t.entry_time.strftime('%H:%M:%S') if t.entry_time else "None"
            exit_t = t.exit_time.strftime('%H:%M:%S') if t.exit_time else "None"
            print(f"ID: {t.id} | Symbol: {t.symbol} | Status: {status} | Entry: {entry_t} | Exit: {exit_t} | PnL: {t.pnl}")

if __name__ == "__main__":
    asyncio.run(main())
