import asyncio
from app.database.base import AsyncSessionLocal
from app.services.pnl_engine import compute_live_pnl
from app.strategies.registry import get_registry

async def test_gather():
    registry = get_registry()
    print("Testing asyncio.gather with shared session...")
    async with AsyncSessionLocal() as db:
        tasks = [compute_live_pnl(db, sid, 25000) for sid in registry]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for sid, pnl in zip(registry, results):
            if isinstance(pnl, Exception):
                print(f"Exception for {sid}: {repr(pnl)}")
            else:
                print(f"Success for {sid}: {pnl['total_equity']}")

if __name__ == "__main__":
    asyncio.run(test_gather())
