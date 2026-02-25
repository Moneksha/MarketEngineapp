import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from app.config.settings import settings

async def main():
    engine = create_async_engine(settings.database_url, echo=True)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        # Delete invalid snapshots specifically for ema_9_crossover_option_selling 
        result = await session.execute(text("DELETE FROM pnl_snapshots WHERE strategy_id = 'ema_9_crossover_option_selling' AND unrealized_pnl < -10000 RETURNING id, strategy_id, unrealized_pnl"))
        deleted_snaps = result.fetchall()
        for s in deleted_snaps:
            print(f"Deleted PnL Snapshot: ID {s[0]}, Strategy {s[1]}, Unrealized {s[2]}")
        
        await session.commit()
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
