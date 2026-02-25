"""
Strategy API Routes
GET  /api/strategies              — list all strategies
GET  /api/strategies/{id}         — strategy details + metadata
POST /api/strategies/{id}/start   — start paper trading for strategy
POST /api/strategies/{id}/stop    — stop paper trading for strategy
POST /api/strategies/{id}/backtest— run historical backtest
GET  /api/strategies/{id}/live    — live trade status + PnL
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional
from loguru import logger

from app.database.base import get_db
from app.database.models import Strategy, BacktestResult
from app.strategies.registry import get_registry, get_strategy, list_strategies
from app.services.kite_service import kite_service, INSTRUMENT_TOKENS
from app.utils.indicators import candles_to_dataframe
from app.services import paper_trading_engine as pta
from app.services.pnl_engine import compute_live_pnl, get_equity_curve, get_todays_trades
from app.utils.email_sender import send_strategy_request_email

router = APIRouter(prefix="/api/strategies", tags=["strategies"])


class StrategyRequest(BaseModel):
    name: str
    phone: str
    email: str
    description: str


@router.post("/request")
async def submit_strategy_request(req: StrategyRequest):
    """Accept a strategy request form and email it to the configured address."""
    ok = await send_strategy_request_email(
        name=req.name,
        phone=req.phone,
        email=req.email,
        description=req.description,
    )
    return {
        "status": "received",
        "emailed": ok,
        "message": "Your strategy request has been received!" + (
            " We'll be in touch soon." if ok else
            " (Email delivery pending SMTP setup — request logged.)"
        ),
    }




@router.get("")
async def get_all_strategies():
    return {"strategies": list_strategies()}


@router.get("/{strategy_id}")
async def get_strategy_detail(strategy_id: str):
    try:
        strategy = get_strategy(strategy_id)
        meta = strategy.get_metadata()
        active = pta.get_active_trade(strategy_id)
        meta["active_trade"] = active
        return meta
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Strategy '{strategy_id}' not found")


@router.post("/{strategy_id}/start")
async def start_strategy(strategy_id: str, db: AsyncSession = Depends(get_db)):
    try:
        strategy = get_strategy(strategy_id)
        strategy.start()

        # Upsert strategy record in DB
        from sqlalchemy import select
        result = await db.execute(select(Strategy).where(Strategy.id == strategy_id))
        db_strat = result.scalar_one_or_none()
        if not db_strat:
            db_strat = Strategy(
                id=strategy.strategy_id,
                name=strategy.name,
                timeframe=strategy.timeframe,
                description=strategy.description,
                is_active=True,
            )
            db.add(db_strat)
        else:
            db_strat.is_active = True
        await db.commit()

        logger.info(f"Strategy [{strategy_id}] started")
        return {"status": "started", "strategy_id": strategy_id}
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Strategy '{strategy_id}' not found")


@router.post("/{strategy_id}/stop")
async def stop_strategy(strategy_id: str, db: AsyncSession = Depends(get_db)):
    try:
        strategy = get_strategy(strategy_id)
        strategy.stop()

        from sqlalchemy import select
        result = await db.execute(select(Strategy).where(Strategy.id == strategy_id))
        db_strat = result.scalar_one_or_none()
        if db_strat:
            db_strat.is_active = False
            await db.commit()

        logger.info(f"Strategy [{strategy_id}] stopped")
        return {"status": "stopped", "strategy_id": strategy_id}
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Strategy '{strategy_id}' not found")


@router.post("/{strategy_id}/backtest")
async def run_backtest(
    strategy_id: str,
    days: int = Query(30, description="Number of days of historical data"),
    db: AsyncSession = Depends(get_db),
):
    if not kite_service.is_authenticated():
        raise HTTPException(status_code=401, detail="Not authenticated with Zerodha")

    try:
        strategy = get_strategy(strategy_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Strategy '{strategy_id}' not found")

    from datetime import datetime, timedelta
    try:
        token = INSTRUMENT_TOKENS["NIFTY 50"]
        to_dt = datetime.now()
        from_dt = to_dt - timedelta(days=days)

        from app.strategies.registry import TIMEFRAME_MAP
        kite_interval = TIMEFRAME_MAP.get(strategy.timeframe, "5minute")
        candles = await kite_service.get_historical(token, from_dt, to_dt, kite_interval)
        df = candles_to_dataframe(candles)

        if df.empty:
            raise HTTPException(status_code=400, detail="No historical data available")

        result = strategy.backtest(df)

        # Cache result in DB
        from datetime import date
        bt = BacktestResult(
            strategy_id=strategy_id,
            run_date=date.today(),
            from_date=from_dt.date(),
            to_date=to_dt.date(),
            total_trades=result["total_trades"],
            winning_trades=result["winning_trades"],
            losing_trades=result["losing_trades"],
            win_rate=result["win_rate"],
            total_pnl=result["total_pnl"],
            max_profit=result["max_profit"],
            max_loss=result["max_loss"],
            max_drawdown=result["max_drawdown"],
            equity_curve=result["equity_curve"],
        )
        db.add(bt)
        await db.commit()

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Backtest error [{strategy_id}]: {e}")
        raise HTTPException(status_code=500, detail=str(e))



@router.post("/{strategy_id}/reset-trade")
async def reset_active_trade(strategy_id: str, db: AsyncSession = Depends(get_db)):
    """Debug: clear in-memory active trade and reset strategy daily flag."""
    from app.services.paper_trading_engine import _active_trades
    removed = _active_trades.pop(strategy_id, None)
    # Reset the strategy's daily traded flag so it can enter again
    try:
        strategy = get_strategy(strategy_id)
        strategy._has_traded_today = False
    except Exception:
        pass
    return {
        "status": "cleared",
        "strategy_id": strategy_id,
        "had_trade": removed is not None,
    }


@router.get("/{strategy_id}/live")
async def get_live_status(strategy_id: str, db: AsyncSession = Depends(get_db)):
    try:
        get_strategy(strategy_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Strategy '{strategy_id}' not found")

    try:
        nifty = await kite_service.get_nifty_quote() if kite_service.is_authenticated() else {}
        nifty_spot = float(nifty.get("last_price", 0)) if nifty else 0

        active_trade = pta.get_active_trade(strategy_id)

        # For straddle strategies, use real combined premium as current_price for PnL
        current_price = nifty_spot
        if active_trade:
            trade_sym = active_trade.get("symbol", "")
            sig_data = active_trade.get("signal_data") or {}
            inner = sig_data.get("signal_data") or sig_data   # unwrap double-nested structure
            if "STRADDLE" in trade_sym:
                sell_leg = inner.get("sell_leg", {})
                buy_leg  = inner.get("buy_leg", {})
                if sell_leg.get("symbol") and buy_leg.get("symbol"):
                    try:
                        q = await kite_service.get_quote([sell_leg["symbol"], buy_leg["symbol"]])
                        ce_p = float(q.get(sell_leg["symbol"], {}).get("last_price") or sell_leg.get("price", 0))
                        pe_p = float(q.get(buy_leg["symbol"],  {}).get("last_price") or buy_leg.get("price", 0))
                        if ce_p > 0 and pe_p > 0:
                            current_price = ce_p + pe_p
                    except Exception as e:
                        logger.warning(f"Could not fetch straddle live price: {e}")

        pnl_data = await compute_live_pnl(db, strategy_id, current_price)
        today_trades = await get_todays_trades(db, strategy_id)
        equity_curve = await get_equity_curve(db, strategy_id, limit=100)

        return {
            "strategy_id": strategy_id,
            "is_running": get_strategy(strategy_id).is_running,
            "current_price": current_price,
            "trade_status": "ACTIVE" if active_trade else ("NO_TRADE" if not today_trades else "CLOSED"),
            "pnl": pnl_data,
            "today_trades": today_trades,
            "equity_curve": equity_curve,
        }
    except Exception as e:
        logger.error(f"Live status error [{strategy_id}]: {e}")
        raise HTTPException(status_code=500, detail=str(e))
