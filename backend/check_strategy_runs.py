import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from app.config.settings import settings

async def main():
    engine = create_async_engine(settings.database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        result = await session.execute(text("""
            SELECT id, run_at, signal, price, candle_data 
            FROM strategy_runs 
            WHERE strategy_id = 'straddle_2a_vanilla' 
            ORDER BY run_at DESC 
            LIMIT 10
        """))
        runs = result.fetchall()
        print(f"Total Runs Found: {len(runs)}")
        for r in runs:
            print(f"ID: {r[0]} | Time: {r[1]} | Signal: {r[2]} | Price: {r[3]} | Data: {r[4]}")
            
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
