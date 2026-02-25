import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from app.config.settings import settings

async def main():
    engine = create_async_engine(settings.database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        # Delete the fake straddle trades
        await session.execute(text("DELETE FROM trades WHERE strategy_id = 'straddle_2a_vanilla' AND status = 'UNIVERSAL_EXIT';"))
        
        # Delete corrupted pnl snapshots
        await session.execute(text("DELETE FROM pnl_snapshots WHERE strategy_id = 'straddle_2a_vanilla' AND unrealized_pnl < -100000;"))
        
        await session.commit()
        print("Data cleaned.")
            
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
