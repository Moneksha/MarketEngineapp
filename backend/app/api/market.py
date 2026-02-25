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
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from loguru import logger
from fastapi.responses import RedirectResponse
from app.config.settings import settings

from app.services.kite_service import kite_service, INSTRUMENT_TOKENS
from app.services.market_bias import compute_market_bias

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
    Receives the redirect from Zerodha Kite.
    Exchanges request_token for access_token immediately on the backend.
    Redirects back to the frontend dashboard.
    """
    # 'status' is returned by Kite (success/failure)
    if status == "success" or action == "login":
        if request_token:
            try:
                await kite_service.exchange_token(request_token)
                logger.info("Secure OAuth callback successfully exchanged token.")
            except Exception as e:
                logger.error(f"Secure OAuth callback token exchange failed: {e}")
    
    # Redirect to the frontend dashboard
    # Remove any sensitive tokens from the URL
    dashboard_url = settings.frontend_url
    return RedirectResponse(url=dashboard_url, status_code=302)


@router.get("/auth/zerodha/status")
async def secure_auth_status():
    """Returns whether the backend possesses a valid access token."""
    if not kite_service.is_authenticated():
        return {"connected": False}
    
    # Actually verify the token works by fetching the profile
    profile = await kite_service.get_profile()
    if not profile or "user_id" not in profile:
        # Token is invalid or expired
        kite_service.set_access_token("") # Clear it
        return {"connected": False}
        
    return {"connected": True}


@router.get("/nifty")
async def get_nifty():
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
async def get_heavyweights():
    if not kite_service.is_authenticated():
        raise HTTPException(status_code=401, detail="Not authenticated with Zerodha")
    try:
        data = await kite_service.get_heavyweight_quotes()
        return {"stocks": list(data.values())}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/bias")
async def get_market_bias():
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
    days: int = Query(5),
):
    if not kite_service.is_authenticated():
        raise HTTPException(status_code=401, detail="Not authenticated with Zerodha")
    token = INSTRUMENT_TOKENS.get(symbol.upper())
    if not token:
        raise HTTPException(status_code=404, detail=f"Symbol '{symbol}' not found")
    from datetime import datetime, timedelta
    to_dt = datetime.now()
    from_dt = to_dt - timedelta(days=days)
    try:
        candles = await kite_service.get_historical(token, from_dt, to_dt, interval)
        return {"symbol": symbol, "interval": interval, "candles": candles}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



