import asyncio
from datetime import datetime
from app.database.base import AsyncSessionLocal
from app.services.pnl_engine import compute_live_pnl
from app.services.paper_trading_engine import _active_trades
from app.services.kite_service import kite_service

async def run():
    _active_trades["ema_21_option_selling"] = {
        "strategy_id": "ema_21_option_selling",
        "symbol": "NFO:NIFTY26FEB25700PE",
        "direction": "SELL",
        "entry_price": 97.4,
        "entry_time": datetime.now(),
        "sl_price": None,
        "target_price": None,
        "quantity": 50,
        "status": "ACTIVE"
    }

    # Authenticate (it should already be authenticated if running, but we might need to load_instruments if testing)
    print("Testing get_quote directly:")
    symbols_to_test = ["NFO:NIFTY26FEB25700PE", "NFO:NIFTY27FEB25700PE"]
    q = await kite_service.get_quote(symbols_to_test)
    print("Quote response:", q)

    async with AsyncSessionLocal() as db:
        pnl = await compute_live_pnl(db, "ema_21_option_selling", 25689.6)
        print("PnL Response:")
        print(pnl)

if __name__ == "__main__":
    asyncio.run(run())
