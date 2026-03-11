"""
Trades & PnL API Routes
GET /api/trades                   — all trades (with filters)
GET /api/trades/today             — today's trades (all strategies)
GET /api/pnl/{strategy_id}        — PnL data + equity curve
GET /api/pnl/all                  — aggregate PnL across all strategies
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional
from datetime import date, datetime

from app.database.base import get_db
from app.database.models import Trade, PnLSnapshot, User
from app.api.deps import get_current_user
from app.services.pnl_engine import get_equity_curve, compute_live_pnl
from app.services.kite_service import kite_service

trades_router = APIRouter(
    prefix="/api/trades", 
    tags=["trades"],
    dependencies=[Depends(get_current_user)]
)
pnl_router = APIRouter(
    prefix="/api/pnl", 
    tags=["pnl"],
    dependencies=[Depends(get_current_user)]
)


@trades_router.get("")
async def list_trades(
    strategy_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(50),
    db: AsyncSession = Depends(get_db),
):
    q = select(Trade).order_by(Trade.entry_time.desc()).limit(limit)
    if strategy_id:
        q = q.where(Trade.strategy_id == strategy_id)
    if status:
        q = q.where(Trade.status == status)
    result = await db.execute(q)
    trades = result.scalars().all()
    return {
        "trades": [
            {
                "id": t.id,
                "strategy_id": t.strategy_id,
                "symbol": t.symbol,
                "direction": t.direction,
                "market_bias": t.signal_data.get("market_bias") if isinstance(t.signal_data, dict) else (t.signal_data.get("regime") if isinstance(t.signal_data, dict) else None),
                "entry_price": float(t.entry_price),
                "exit_price": float(t.exit_price) if t.exit_price else None,
                "sl_price": float(t.sl_price) if t.sl_price else None,
                "target_price": float(t.target_price) if t.target_price else None,
                "pnl": float(t.pnl) if t.pnl else None,
                "quantity": t.quantity,
                "status": t.status,
                "entry_time": t.entry_time.isoformat(),
                "exit_time": t.exit_time.isoformat() if t.exit_time else None,
            }
            for t in trades
        ]
    }


@trades_router.get("/today")
async def get_today_trades(db: AsyncSession = Depends(get_db)):
    today = date.today()
    result = await db.execute(
        select(Trade)
        .where(func.date(Trade.entry_time) == today)
        .order_by(Trade.entry_time.desc())
    )
    trades = result.scalars().all()
    return {
        "date": str(today),
        "trades": [
            {
                "id": t.id,
                "strategy_id": t.strategy_id,
                "symbol": t.symbol,
                "direction": t.direction,
                "market_bias": t.signal_data.get("market_bias") if isinstance(t.signal_data, dict) else (t.signal_data.get("regime") if isinstance(t.signal_data, dict) else None),
                "entry_price": float(t.entry_price),
                "exit_price": float(t.exit_price) if t.exit_price else None,
                "pnl": float(t.pnl) if t.pnl else None,
                "status": t.status,
                "entry_time": t.entry_time.isoformat(),
                "exit_time": t.exit_time.isoformat() if t.exit_time else None,
            }
            for t in trades
        ],
        "total_pnl": sum(float(t.pnl or 0) for t in trades),
    }


@pnl_router.get("/all")
async def get_all_pnl(db: AsyncSession = Depends(get_db)):
    from app.strategies.registry import get_registry
    from app.services import paper_trading_engine as pta

    nifty = await kite_service.get_nifty_quote() if kite_service.is_authenticated() else {}
    nifty_spot = float(nifty.get("last_price", 0)) if nifty else 0

    registry = get_registry()
    result = []
    for strategy_id in registry:
        current_price = nifty_spot
        # Resolve combined CE+PE premium for straddle strategies
        active_trade = pta.get_active_trade(strategy_id)
        if active_trade:
            trade_sym = active_trade.get("symbol", "")
            if "STRADDLE" in trade_sym:
                sig_data = active_trade.get("signal_data") or {}
                inner = sig_data.get("signal_data") or sig_data
                sell_leg = inner.get("sell_leg", {})
                buy_leg  = inner.get("buy_leg", {})
                if sell_leg.get("symbol") and buy_leg.get("symbol"):
                    try:
                        q = await kite_service.get_quote([sell_leg["symbol"], buy_leg["symbol"]])
                        ce_p = float(q.get(sell_leg["symbol"], {}).get("last_price") or sell_leg.get("price", 0))
                        pe_p = float(q.get(buy_leg["symbol"],  {}).get("last_price") or buy_leg.get("price", 0))
                        if ce_p > 0 and pe_p > 0:
                            current_price = ce_p + pe_p
                    except Exception:
                        pass
        pnl = await compute_live_pnl(db, strategy_id, current_price)
        result.append(pnl)
    return {"pnl_summary": result, "timestamp": datetime.now().isoformat()}


@pnl_router.get("/{strategy_id}")
async def get_strategy_pnl(strategy_id: str, db: AsyncSession = Depends(get_db)):
    from app.services import paper_trading_engine as pta

    nifty = await kite_service.get_nifty_quote() if kite_service.is_authenticated() else {}
    current_price = float(nifty.get("last_price", 0)) if nifty else 0

    # For straddle strategies, use combined CE+PE premium as current_price
    active_trade = pta.get_active_trade(strategy_id)
    if active_trade:
        trade_sym = active_trade.get("symbol", "")
        if "STRADDLE" in trade_sym:
            sig_data = active_trade.get("signal_data") or {}
            inner = sig_data.get("signal_data") or sig_data  # unwrap double-nested
            sell_leg = inner.get("sell_leg", {})
            buy_leg  = inner.get("buy_leg", {})
            if sell_leg.get("symbol") and buy_leg.get("symbol"):
                try:
                    q = await kite_service.get_quote([sell_leg["symbol"], buy_leg["symbol"]])
                    ce_p = float(q.get(sell_leg["symbol"], {}).get("last_price") or sell_leg.get("price", 0))
                    pe_p = float(q.get(buy_leg["symbol"],  {}).get("last_price") or buy_leg.get("price", 0))
                    if ce_p > 0 and pe_p > 0:
                        current_price = ce_p + pe_p
                except Exception:
                    pass

    pnl = await compute_live_pnl(db, strategy_id, current_price)
    equity_curve = await get_equity_curve(db, strategy_id, limit=200)
    pnl["equity_curve"] = equity_curve
    return pnl

