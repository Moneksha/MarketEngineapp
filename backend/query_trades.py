import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from app.config.settings import settings

async def main():
    engine = create_async_engine(settings.database_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        result = await session.execute(text("SELECT id, strategy_id, symbol, status FROM trades ORDER BY created_at DESC LIMIT 10"))
        trades = result.fetchall()
        for t in trades:
            print(f"ID: {t[0]}, Strategy: {t[1]}, Symbol: {t[2]}, Status: {t[3]}")
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
