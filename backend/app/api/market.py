"""
Market Data API Routes
GET /api/market/nifty         — live NIFTY quote
GET /api/market/bias          — market bias (Bullish/Bearish/Sideways)
GET /api/market/heavyweights  — heavyweight stocks + NIFTY impact
GET /api/market/ohlc/{symbol} — historical OHLC candles
POST /api/market/auth/zerodha/login — returns Zerodha login URL
GET /api/market/auth/zerodha/callback — handles redirect from Zerodha
GET /api/market/auth/zerodha/status — returns connection status
"""
import asyncio
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel
from typing import Optional
from loguru import logger
from fastapi.responses import RedirectResponse
from app.config.settings import settings
from app.services.kite_service import kite_service, INSTRUMENT_TOKENS
from app.services.market_bias import compute_market_bias
from app.database.models import User
from app.api.deps import get_current_user

router = APIRouter(prefix="/api/market", tags=["market"])


class AuthRequest(BaseModel):
    request_token: str


class TokenRequest(BaseModel):
    access_token: str


@router.get("/login-url")
async def get_login_url():
    """Legacy route for login URL"""
    return {"login_url": kite_service.get_login_url()}


@router.post("/auth")
async def exchange_token(req: AuthRequest):
    """Legacy route for frontend token exchange"""
    try:
        access_token = await kite_service.exchange_token(req.request_token)
        profile = await kite_service.get_profile()
        return {
            "status": "ok",
            "access_token": access_token,
            "user_name": profile.get("user_name", ""),
            "email": profile.get("email", ""),
        }
    except Exception as e:
        logger.error(f"Token exchange failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/set-token")
async def set_access_token(req: TokenRequest):
    """Directly set a known access token (skip request_token exchange)."""
    kite_service.set_access_token(req.access_token)
    return {"status": "ok", "message": "Access token set"}


@router.get("/status")
async def legacy_auth_status():
    """Legacy route for auth status"""
    return {
        "authenticated": kite_service.is_authenticated(),
        "api_key": kite_service.is_authenticated() and True,
    }


# --- NEW SECURE OAUTH ROUTES ---

@router.post("/auth/zerodha/login")
async def secure_login_url():
    """Returns the Kite Login URL for the frontend to redirect to."""
    return {"login_url": kite_service.get_login_url()}


@router.get("/auth/zerodha/callback")
async def auth_callback(request_token: str = Query(...), action: Optional[str] = Query(None), status: Optional[str] = Query(None)):
    """
    Receives the redirect from Zerodha Kite (or the Playwright script).
    Exchanges request_token for access_token immediately on the backend.
    """
    if request_token:
        try:
            await kite_service.exchange_token(request_token)
            logger.info("Secure OAuth callback successfully exchanged token.")
        except Exception as e:
            logger.error(f"Secure OAuth callback token exchange failed: {e}")
    
    # Redirect to the frontend dashboard
    dashboard_url = settings.frontend_url
    return RedirectResponse(url=dashboard_url, status_code=302)


@router.post("/auth/zerodha/auto-login")
async def trigger_auto_login():
    """
    Triggers the Playwright auto-login script in the background.
    The script runs independently, fetches the request token, and sends it 
    back to the /auth/zerodha/callback endpoint.
    """
    import subprocess
    import os
    import sys
    
    script_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "scripts", "kite_auto_login.py")
    
    try:
        # Run in background without blocking the API response
        subprocess.Popen([sys.executable, script_path])
        return {"status": "success", "message": "Auto-login process started in the background."}
    except Exception as e:
        logger.error(f"Failed to start auto-login script: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/auth/zerodha/status")
async def secure_auth_status():
    """Returns whether the backend possesses a valid access token."""
    if not kite_service.is_authenticated():
        return {"connected": False}
    
    # Actually verify the token works by fetching the profile
    try:
        profile = await kite_service.get_profile()
        if not profile or "user_id" not in profile:
            # Empty profile might mean token isn't working or mocked empty
            if not settings.mock_mode:
                kite_service.set_access_token("") # Clear it
                return {"connected": False}
    except Exception as e:
        from kiteconnect.exceptions import TokenException
        if isinstance(e, TokenException):
            logger.error(f"Token is invalid/expired according to Kite: {e}")
            kite_service.set_access_token("") # Clear it
            return {"connected": False}
        elif "token" in str(e).lower() and "exception" in str(type(e)).lower():
             logger.error(f"Possible token exception, clearing it: {e}")
             kite_service.set_access_token("")
             return {"connected": False}
        
        logger.warning(f"Network or non-token error verifying profile: {e}")
        # Return True so frontend doesn't log the user out
        return {"connected": True}
        
    return {"connected": True}


@router.get("/nifty")
async def get_nifty(current_user: User = Depends(get_current_user)):
    if not kite_service.is_authenticated():
        raise HTTPException(status_code=401, detail="Not authenticated with Zerodha")
    try:
        quote, vix = await asyncio.gather(
            kite_service.get_nifty_quote(),
            kite_service.get_vix_quote(),
            return_exceptions=True,
        )
        if isinstance(quote, Exception):
            raise quote
        if isinstance(vix, Exception):
            vix = {"ltp": 0, "change": 0, "change_pct": 0}
        return {
            "symbol": "NIFTY 50",
            "ltp": quote.get("last_price", 0),
            "change": quote.get("change", 0) or quote.get("net_change", 0),
            "change_pct": round((quote.get("net_change", 0) / quote.get("ohlc", {}).get("close", 1)) * 100, 2) if quote.get("ohlc", {}).get("close", 0) else 0,
            "open": quote.get("ohlc", {}).get("open", 0),
            "high": quote.get("ohlc", {}).get("high", 0),
            "low": quote.get("ohlc", {}).get("low", 0),
            "close": quote.get("ohlc", {}).get("close", 0),
            "volume": quote.get("volume", 0),
            "timestamp": str(quote.get("timestamp", "")),
            "vix": vix,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/heavyweights")
async def get_heavyweights(current_user: User = Depends(get_current_user)):
    if not kite_service.is_authenticated():
        raise HTTPException(status_code=401, detail="Not authenticated with Zerodha")
    try:
        data = await kite_service.get_heavyweight_quotes()
        return {"stocks": list(data.values())}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/bias")
async def get_market_bias(current_user: User = Depends(get_current_user)):
    if not kite_service.is_authenticated():
        raise HTTPException(status_code=401, detail="Not authenticated with Zerodha")
    try:
        nifty = await kite_service.get_nifty_quote()
        heavyweights = await kite_service.get_heavyweight_quotes()
        change_pct = float(nifty.get("net_change", 0))
        bias = await compute_market_bias(change_pct, heavyweights)
        return bias
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ohlc/{symbol}")
async def get_ohlc(
    symbol: str,
    interval: str = Query("5minute"),
    days: int = Query(1),
    current_user: User = Depends(get_current_user)
):
    if not kite_service.is_authenticated():
        raise HTTPException(status_code=401, detail="Not authenticated with Zerodha")
    token = INSTRUMENT_TOKENS.get(symbol.upper())
    if not token:
        raise HTTPException(status_code=404, detail=f"Symbol '{symbol}' not found")

    from datetime import datetime, timedelta
    import pytz
    from sqlalchemy import select
    from app.database.base import AsyncSessionLocal
    from app.database.models import NiftyCandle
    from app.utils.indicators import prepare_chart_data

    ist = pytz.timezone("Asia/Kolkata")
    now_ist = datetime.now(ist)

    # 1. Determine the exact start range for fetching (Yesterday Open to Now)
    if now_ist.weekday() == 0:  # Monday
        yesterday_dt = now_ist - timedelta(days=3) # Last Friday
    else:
        yesterday_dt = now_ist - timedelta(days=1)
        
    yesterday_open = ist.localize(datetime(yesterday_dt.year, yesterday_dt.month, yesterday_dt.day, 9, 0, 0))

    # 2. Fetch all 1-minute candles from DB in this range
    async with AsyncSessionLocal() as db:
        stmt = select(NiftyCandle).filter(
            NiftyCandle.symbol == symbol.upper(),
            NiftyCandle.interval == "1minute",
            NiftyCandle.timestamp >= yesterday_open
        ).order_by(NiftyCandle.timestamp.asc())
        
        result = await db.execute(stmt)
        db_candles = result.scalars().all()

    # Convert DB models to dict structure expected by prepare_chart_data
    candles_1m = []
    for c in db_candles:
        # DB returns UTC-aware datetime. Convert to IST naive for indicator processing.
        t_ist = c.timestamp.astimezone(ist).replace(tzinfo=None) if c.timestamp.tzinfo else c.timestamp
        candles_1m.append({
            "date": t_ist,
            "open": float(c.open),
            "high": float(c.high),
            "low": float(c.low),
            "close": float(c.close),
            "volume": int(c.volume)
        })

    # 3. Fallback: If DB is empty, fetch from Kite and construct same range
    if not candles_1m:
        logger.warning(f"[ohlc] No DB candles found for {symbol} since {yesterday_open.date()}. Fetching from Kite.")
        try:
            candles_1m = await kite_service.get_historical(token, yesterday_open, now_ist, "minute")
            # Exclude the live forming candle if we are mid-minute
            if candles_1m and candles_1m[-1].get("volume", 1) == 0: # Approximation for forming
                candles_1m = candles_1m[:-1]
        except Exception as e:
            logger.error(f"[ohlc] Kite fallback fetch failed: {e}")
            raise HTTPException(status_code=500, detail="Failed to fetch market data")

    if not candles_1m:
        return {"symbol": symbol, "interval": interval, "candles": []}

    # 4. Predict how many candles make up "Today" for the display slice
    # Normal day is ~375 1-min candles. In 5min that's 75 candles.
    # We find how many candles in the 1m set belong to *today* to derive our return limit.
    today_str = str(now_ist.date())
    today_1m_count = sum(1 for c in candles_1m if str(c.get("date", "")).startswith(today_str))

    # Calculate target length based on the chosen interval
    interval_minutes = 1
    if "minute" in interval.lower():
        try:
            interval_minutes = int(interval.replace("minute", ""))
        except ValueError:
            interval_minutes = 1 # default to 1 if parsing fails e.g 'minute'
            
    # Calculate how many display candles 'today' actually spans in the new timeframe
    # +1 to ensure partial/latest candle is included
    target_length = max(1, (today_1m_count // interval_minutes) + 1) if today_1m_count > 0 else 75

    # 5. Resample, compute indicators on FULL dataset, and slice
    try:
        final_candles = prepare_chart_data(candles_1m, interval, return_length=target_length)
        logger.info(f"[ohlc] Served {len(final_candles)} contiguous candles for {symbol} ({interval}) derived from {len(candles_1m)} base 1-minute DB candles.")
        return {"symbol": symbol, "interval": interval, "candles": final_candles}
    except Exception as e:
        logger.error(f"[ohlc] Processing error: {e}")
        raise HTTPException(status_code=500, detail="Failed to process market data")



