"""
Paper Trading Engine
Executes virtual paper trades. NO real orders are ever placed.
Manages one trade per strategy: entry, SL/target monitoring, EOD square-off.
"""
import asyncio
from datetime import datetime, time
from typing import Dict, Optional, Any
from loguru import logger
from app.config.settings import settings

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.database.models import Trade

# In-memory active trades: strategy_id → trade dict
_active_trades: Dict[str, Dict] = {}


async def load_active_trades(db: AsyncSession):
    """Restore active trades from DB on startup.
    
    Trades that were ACTIVE on a previous calendar day are stale — the market
    closed and never squared them off (e.g. backend was down at EOD).
    We close those immediately with status='EOD' and do NOT load them into
    the in-memory dict, so today starts clean.
    """
    from datetime import date
    today = date.today()

    result = await db.execute(
        select(Trade).where(Trade.status == "ACTIVE")
    )
    trades = result.scalars().all()

    restored = 0
    stale_closed = 0
    from app.strategies.registry import get_registry
    registry = get_registry()

    for t in trades:
        trade_date = t.entry_time.date() if t.entry_time else None
        
        # Determine if the strategy was marked positional
        strat = registry.get(t.strategy_id)
        is_positional = strat.is_positional if strat else False

        # If the trade is from a previous day and NOT positional, it's stale — close it in DB
        if trade_date and trade_date < today and not is_positional:
            stmt = (
                update(Trade)
                .where(Trade.id == t.id)
                .values(
                    status="EOD",
                    exit_price=t.entry_price,   # best we can do without live price
                    exit_time=datetime.now(),
                    pnl=0.0,
                )
            )
            await db.execute(stmt)
            stale_closed += 1
            logger.warning(
                f"[startup] Closed stale trade id={t.id} strategy={t.strategy_id} "
                f"from {trade_date} (market was closed when backend restarted)"
            )
            continue

        # Today's trade — restore to memory
        _active_trades[t.strategy_id] = {
            "id": t.id,
            "strategy_id": t.strategy_id,
            "symbol": t.symbol,
            "direction": t.direction,
            "entry_price": float(t.entry_price),
            "entry_time": t.entry_time,
            "sl_price": float(t.sl_price) if t.sl_price else None,
            "target_price": float(t.target_price) if t.target_price else None,
            "quantity": t.quantity,
            "status": t.status,
            "signal_data": t.signal_data,
            "unrealized_pnl": 0.0,
        }
        restored += 1

    await db.commit()
    logger.info(f"[startup] Restored {restored} active trades | Closed {stale_closed} stale trades from previous days")



def is_market_open() -> bool:
    import pytz
    ist = pytz.timezone("Asia/Kolkata")
    now = datetime.now(ist).time()
    open_h, open_m = map(int, settings.market_open.split(":"))
    close_h, close_m = map(int, settings.market_close.split(":"))
    market_open = time(open_h, open_m)
    market_close = time(close_h, close_m)
    return market_open <= now <= market_close


def is_eod_squareoff_time() -> bool:
    import pytz
    ist = pytz.timezone("Asia/Kolkata")
    now = datetime.now(ist).time()
    sq_h, sq_m = map(int, settings.eod_square_off.split(":"))
    eod_time = time(sq_h, sq_m)
    return now >= eod_time


def get_active_trade(strategy_id: str) -> Optional[Dict]:
    return _active_trades.get(strategy_id)


def has_active_trade(strategy_id: str) -> bool:
    return strategy_id in _active_trades


async def execute_paper_trade(
    db: AsyncSession,
    strategy_id: str,
    signal: Dict[str, Any],
    quantity: int = None,
) -> Dict[str, Any]:
    """
    Execute a paper trade for a strategy.
    Returns the trade dict. Does NOT write to DB (caller does that).
    """
    if has_active_trade(strategy_id):
        logger.debug(f"[{strategy_id}] Skipped: already has active trade")
        return {}

    if not is_market_open():
        logger.warning(f"[{strategy_id}] Skipped: market closed")
        return {}

    qty = quantity or settings.default_quantity
    entry_price = signal["price"]
    direction = signal["signal"]          # BUY or SELL

    trade = {
        "strategy_id": strategy_id,
        "symbol": signal.get("symbol", "NIFTY 50"),
        "direction": direction,
        "entry_price": entry_price,
        "entry_time": datetime.now(),
        "sl_price": signal.get("sl"),
        "target_price": signal.get("target"),
        "quantity": qty,
        "status": "ACTIVE",
        "signal_data": signal,
        "unrealized_pnl": 0.0,
    }

    # Persist to DB
    trade_db = await _save_new_trade(db, trade)
    trade["id"] = trade_db.id

    _active_trades[strategy_id] = trade
    logger.info(
        f"[{strategy_id}] Paper trade ENTERED: {direction} @ {entry_price} "
        f"| SL={signal.get('sl')} | TGT={signal.get('target')} | Qty={qty}"
    )
    return trade


async def tick_check(db: AsyncSession, strategy_id: str, current_price: float) -> Optional[Dict]:
    """
    Check if SL/target is hit for active trade. Returns exit info if closed.
    """
    trade = _active_trades.get(strategy_id)
    if not trade:
        return None

    direction = trade["direction"]
    sl = trade["sl_price"]
    target = trade["target_price"]
    entry = trade["entry_price"]
    qty = trade["quantity"]

    # Update unrealized PnL
    if direction == "BUY":
        unrealized = (current_price - entry) * qty
    else:
        unrealized = (entry - current_price) * qty
    _active_trades[strategy_id]["unrealized_pnl"] = round(unrealized, 2)

    from app.strategies.registry import get_registry
    registry = get_registry()
    strat = registry.get(strategy_id)
    is_positional = strat.is_positional if strat else False

    # EOD square-off (only for intraday trades)
    exit_reason = None
    if is_eod_squareoff_time() and not is_positional:
        exit_reason = "EOD"
    elif direction == "BUY":
        if sl and current_price <= sl:
            exit_reason = "SL_HIT"
        elif target and current_price >= target:
            exit_reason = "TARGET_HIT"
    elif direction == "SELL":
        if sl and current_price >= sl:
            exit_reason = "SL_HIT"
        elif target and current_price <= target:
            exit_reason = "TARGET_HIT"

    if exit_reason:
        if direction == "BUY":
            pnl = (current_price - entry) * qty
        else:
            pnl = (entry - current_price) * qty

        exit_info = {
            **trade,
            "exit_price": current_price,
            "exit_time": datetime.now(),
            "pnl": round(pnl, 2),
            "status": exit_reason,
        }
        
        # Persist update
        await _update_closed_trade(db, trade["id"], exit_info)
        
        del _active_trades[strategy_id]
        logger.info(
            f"[{strategy_id}] Trade EXITED ({exit_reason}) @ {current_price} "
            f"| PnL=₹{pnl:.2f}"
        )
        return exit_info

    return None


async def exit_trade(db: AsyncSession, strategy_id: str, current_price: float, reason: str = "STRATEGY_EXIT") -> Optional[Dict]:
    """Force close an active trade for a specific dynamic reason."""
    trade = _active_trades.get(strategy_id)
    if not trade:
        return None

    direction = trade["direction"]
    entry = trade["entry_price"]
    qty = trade["quantity"]

    if direction == "BUY":
        pnl = (current_price - entry) * qty
    else:
        pnl = (entry - current_price) * qty

    exit_info = {
        **trade,
        "exit_price": current_price,
        "exit_time": datetime.now(),
        "pnl": round(pnl, 2),
        "status": reason,
    }
    
    # Persist update
    await _update_closed_trade(db, trade["id"], exit_info)
    
    del _active_trades[strategy_id]
    logger.info(
        f"[{strategy_id}] Trade EXITED ({reason}) @ {current_price} "
        f"| PnL=₹{pnl:.2f}"
    )
    return exit_info


async def _save_new_trade(db: AsyncSession, trade_data: Dict) -> Trade:
    new_trade = Trade(
        strategy_id=trade_data["strategy_id"],
        symbol=trade_data["symbol"],
        direction=trade_data["direction"],
        entry_price=trade_data["entry_price"],
        entry_time=trade_data["entry_time"],
        sl_price=trade_data.get("sl_price"),
        target_price=trade_data.get("target_price"),
        quantity=trade_data["quantity"],
        status=trade_data["status"],
        signal_data=trade_data.get("signal_data"),
    )
    db.add(new_trade)
    await db.commit()
    await db.refresh(new_trade)
    return new_trade


async def _update_closed_trade(db: AsyncSession, trade_id: int, exit_data: Dict):
    stmt = (
        update(Trade)
        .where(Trade.id == trade_id)
        .values(
            exit_price=exit_data["exit_price"],
            exit_time=exit_data["exit_time"],
            pnl=exit_data["pnl"],
            status=exit_data["status"],
        )
    )
    await db.execute(stmt)
    await db.commit()


def get_all_active_trades() -> Dict[str, Dict]:
    return dict(_active_trades)


async def square_off_all(db: AsyncSession, current_prices: Dict[str, float]):
    """Force close all active INTRADAY trades at EOD."""
    from app.strategies.registry import get_registry
    registry = get_registry()
    
    for strategy_id in list(_active_trades.keys()):
        strat = registry.get(strategy_id)
        is_positional = strat.is_positional if strat else False
        
        # Only square off intraday trades
        if not is_positional:
            nifty_price = current_prices.get("NIFTY 50", 0)
            if nifty_price:
                await tick_check(db, strategy_id, nifty_price)
