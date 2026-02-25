import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from app.config.settings import settings

async def main():
    engine = create_async_engine(settings.database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        result = await session.execute(text("SELECT id, name, is_active FROM strategies WHERE id = 'straddle_2a_vanilla'"))
        strat = result.fetchone()
        if strat:
            print(f"Strategy: {strat[0]}, is_active: {strat[2]}")
        else:
            print("Strategy not found in database!")
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
