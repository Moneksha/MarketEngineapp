"""
PnL Engine — real-time MTM calculation and equity tracking.
Aggregates realized + unrealized PnL per strategy, generates equity curve.
"""
from datetime import datetime, date
from typing import Dict, List, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from loguru import logger

from app.database.models import Trade, PnLSnapshot
from app.services.paper_trading_engine import get_all_active_trades
from app.services.kite_service import kite_service


async def compute_live_pnl(db: AsyncSession, strategy_id: str, current_price: float) -> Dict:
    """
    Compute live (realtime) PnL for a strategy:
    - Realized PnL: sum of closed trades today
    - Unrealized PnL: from in-memory active trade
    """
    today = date.today()

    # Realized PnL from DB (all closed trades for this strategy)
    result = await db.execute(
        select(
            func.coalesce(func.sum(Trade.pnl), 0).label("realized"),
            func.count(Trade.id).label("trade_count"),
        ).where(
            Trade.strategy_id == strategy_id,
            Trade.status.in_(["SL_HIT", "TARGET_HIT", "EOD", "CLOSED", "STRATEGY_EXIT"]),
        )
    )
    row = result.first()
    realized_pnl = float(row.realized) if row else 0.0
    closed_trade_count = int(row.trade_count) if row else 0

    # Unrealized from in-memory engine
    active_trades = get_all_active_trades()
    active_trade = active_trades.get(strategy_id)
    unrealized_pnl = 0.0
    active_trade_details = None

    if active_trade:
        entry = float(active_trade["entry_price"])
        qty = active_trade["quantity"]
        direction = active_trade["direction"]
        symbol = active_trade.get("symbol", "NIFTY 50")
        
        # If trading an option, fetch real Option quote instead of NIFTY Spot
        trade_price = current_price
        if "NFO" in symbol:
            try:
                q = await kite_service.get_quote([symbol])
                opt = q.get(symbol, {})
                # only replace trade_price if it's a valid 0-or-more price
                if "last_price" in opt:
                     trade_price = float(opt["last_price"])
            except Exception as e:
                logger.error(f"Failed to fetch option quote for PnL engine: {e}")

        if direction == "BUY":
            unrealized_pnl = (trade_price - entry) * qty
        else:
            unrealized_pnl = (entry - trade_price) * qty
        unrealized_pnl = round(unrealized_pnl, 2)

        active_trade_details = {
            "symbol": symbol,
            "direction": direction,
            "entry_price": entry,
            "current_price": trade_price,
            "sl_price": active_trade.get("sl_price"),
            "target_price": active_trade.get("target_price"),
            "quantity": qty,
            "entry_time": active_trade["entry_time"].isoformat(),
            "unrealized_pnl": unrealized_pnl,
        }

    # Count includes closed + currently active trade
    trade_count = closed_trade_count + (1 if active_trade_details else 0)

    total_equity = round(realized_pnl + unrealized_pnl, 2)

    try:
        from app.strategies.registry import get_strategy
        strat = get_strategy(strategy_id)
        capital = getattr(strat, "fund_required", 100000.0)
    except Exception as e:
        logger.warning(f"Failed to get fund_required for {strategy_id}: {e}")
        capital = 100000.0

    roi = round((total_equity / capital) * 100, 2) if capital > 0 else 0.0

    return {
        "strategy_id": strategy_id,
        "realized_pnl": round(realized_pnl, 2),
        "unrealized_pnl": unrealized_pnl,
        "total_equity": total_equity,
        "roi": roi,
        "trade_count": trade_count,
        "active_trade": active_trade_details,
        "timestamp": datetime.now().isoformat(),
    }


async def save_pnl_snapshot(db: AsyncSession, strategy_id: str, pnl_data: Dict):
    """Persist a PnL snapshot for equity curve charting."""
    snap = PnLSnapshot(
        strategy_id=strategy_id,
        realized_pnl=pnl_data["realized_pnl"],
        unrealized_pnl=pnl_data["unrealized_pnl"],
        total_equity=pnl_data["total_equity"],
        trade_count=pnl_data["trade_count"],
    )
    db.add(snap)
    await db.commit()


async def get_equity_curve(db: AsyncSession, strategy_id: str, limit: int = 200) -> List[Dict]:
    """Fetch equity curve data points for a strategy."""
    result = await db.execute(
        select(PnLSnapshot)
        .where(PnLSnapshot.strategy_id == strategy_id)
        .order_by(PnLSnapshot.snapshot_at)
        .limit(limit)
    )
    snaps = result.scalars().all()
    return [
        {
            "time": s.snapshot_at.isoformat(),
            "equity": float(s.total_equity),
            "realized": float(s.realized_pnl),
            "unrealized": float(s.unrealized_pnl),
        }
        for s in snaps
    ]


async def get_todays_trades(db: AsyncSession, strategy_id: str) -> List[Dict]:
    """Get all trades for a strategy today."""
    today = date.today()
    result = await db.execute(
        select(Trade).where(
            Trade.strategy_id == strategy_id,
            func.date(Trade.entry_time) == today,
        ).order_by(Trade.entry_time.desc())
    )
    trades = result.scalars().all()
    return [
        {
            "id": t.id,
            "direction": t.direction,
            "entry_price": float(t.entry_price),
            "exit_price": float(t.exit_price) if t.exit_price else None,
            "sl_price": float(t.sl_price) if t.sl_price else None,
            "target_price": float(t.target_price) if t.target_price else None,
            "pnl": float(t.pnl) if t.pnl else None,
            "status": t.status,
            "entry_time": t.entry_time.isoformat(),
            "exit_time": t.exit_time.isoformat() if t.exit_time else None,
        }
        for t in trades
    ]
