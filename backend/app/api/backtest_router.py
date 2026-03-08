"""
backtest_router.py
------------------
FastAPI router exposing backtest endpoints for the Equity Research Dashboard.
"""

import re
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Query
from app.services.backtest_engine import run_backtest, get_available_symbols

router = APIRouter(prefix="/api/research", tags=["equity-research"])

# ── Timeframe-based max backtest range (years).  None = unlimited ──────────
TIMEFRAME_MAX_YEARS = {
    "1m": 1,
    "2m": 2,
    "3m": 3,
    "5m": 5,
}


def _max_years_for_timeframe(tf: str) -> int | None:
    """Return max allowed backtest range in years, or None if unlimited."""
    if tf in TIMEFRAME_MAX_YEARS:
        return TIMEFRAME_MAX_YEARS[tf]
    # Dynamic: any minute-based TF < 15 → cap generously
    m = re.match(r"^(\d+)m$", tf)
    if m:
        minutes = int(m.group(1))
        if minutes < 15:
            return max(1, minutes)
    return None  # 15m+, hours, days, weeks → unlimited


@router.get("/symbols")
async def symbols():
    """Return available symbols for the backtest dashboard."""
    return {"symbols": get_available_symbols()}


@router.get("/run-backtest")
async def run_backtest_endpoint(
    symbol: str = Query(default="RELIANCE", description="Stock symbol"),
    strategy_id: str = Query(default="ema_trend", description="Strategy ID: ema_trend, ema_crossover, supertrend, rsi, macd, bollinger"),
    ema_period: int | None = Query(default=None, description="EMA period for trend strategy"),
    fast_ema: int | None = Query(default=None, description="Fast EMA period for crossover"),
    slow_ema: int | None = Query(default=None, description="Slow EMA period for crossover"),
    atr_period: int | None = Query(default=None, description="ATR period for supertrend"),
    factor: float | None = Query(default=None, description="Multiplier factor for supertrend"),
    rsi_length: int | None = Query(default=None, description="RSI period length"),
    oversold: int | None = Query(default=None, description="RSI oversold level"),
    overbought: int | None = Query(default=None, description="RSI overbought level"),
    fast_length: int | None = Query(default=None, description="MACD fast EMA length"),
    slow_length: int | None = Query(default=None, description="MACD slow EMA length"),
    macd_length: int | None = Query(default=None, description="MACD signal line length"),
    bb_length: int | None = Query(default=None, description="Bollinger Band SMA length"),
    bb_mult: float | None = Query(default=None, description="Bollinger Band std dev multiplier"),
    from_date: str = Query(default="2016-03-01", alias="from", description="Start date YYYY-MM-DD"),
    to_date: str = Query(default="2025-01-01", alias="to", description="End date YYYY-MM-DD"),
    timeframe: str = Query(default="1D", description="Timeframe: 1m, 5m, 15m, 1h, 1D, 1W"),
):
    """
    Run a specified backtest strategy and return metrics + time series.
    """
    # ── Backend safety: enforce timeframe range limits ──────────────────────
    max_years = _max_years_for_timeframe(timeframe)
    if max_years is not None:
        try:
            dt_from = datetime.strptime(from_date, "%Y-%m-%d")
            dt_to = datetime.strptime(to_date, "%Y-%m-%d")
            max_delta = timedelta(days=int(max_years * 365.25) + 1)
            if (dt_to - dt_from) > max_delta:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"For {timeframe} timeframe, the maximum supported backtest "
                        f"range is {max_years} year{'s' if max_years > 1 else ''}. "
                        f"Please reduce the date range."
                    ),
                )
        except ValueError:
            pass  # Malformed dates are handled downstream

    # Build strategy params from provided query args
    strategy_params = {}
    if strategy_id == "ema_trend":
        strategy_params["ema_period"] = ema_period or 20
    elif strategy_id == "ema_crossover":
        strategy_params["fast_ema"] = fast_ema or 20
        strategy_params["slow_ema"] = slow_ema or 50
    elif strategy_id == "supertrend":
        strategy_params["atr_period"] = atr_period or 10
        strategy_params["factor"] = factor or 3.0
    elif strategy_id == "rsi":
        strategy_params["rsi_length"] = rsi_length or 14
        strategy_params["oversold"] = oversold or 30
        strategy_params["overbought"] = overbought or 70
    elif strategy_id == "macd":
        strategy_params["fast_length"] = fast_length or 12
        strategy_params["slow_length"] = slow_length or 26
        strategy_params["macd_length"] = macd_length or 9
    elif strategy_id == "bollinger":
        strategy_params["bb_length"] = bb_length or 20
        strategy_params["bb_mult"] = bb_mult or 2.0

    try:
        result = run_backtest(
            symbol=symbol,
            strategy_id=strategy_id,
            strategy_params=strategy_params,
            from_date=from_date,
            to_date=to_date,
            timeframe=timeframe,
        )
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Backtest failed: {str(e)}")

