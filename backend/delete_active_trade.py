import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from app.config.settings import settings

async def main():
    engine = create_async_engine(settings.database_url, echo=True)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        # Delete ALL active trades globally to fix the UI
        result = await session.execute(text("DELETE FROM trades WHERE status = 'ACTIVE' RETURNING id, strategy_id, symbol"))
        deleted_trades = result.fetchall()
        for t in deleted_trades:
            print(f"Deleted active trade: ID {t[0]}, Strategy {t[1]}, Symbol {t[2]}")
        
        await session.commit()
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
