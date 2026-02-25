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
            SELECT id, run_at, strategy_id, signal, price, candle_data 
            FROM strategy_runs 
            WHERE strategy_id = 'ema_9_crossover_option_selling'
            ORDER BY run_at DESC 
            LIMIT 10
        """))
        runs = result.fetchall()
        print(f"Total Runs Found: {len(runs)}")
        for r in runs:
            print(f"ID: {r[0]} | Time: {r[1]} | Strategy: {r[2]} | Signal: {r[3]} | Price: {r[4]} | Data: {r[5]}")
            
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
