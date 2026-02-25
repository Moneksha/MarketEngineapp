"""
FastAPI Application Entry Point — Market Engine
Sets up: database tables, CORS, routers, APScheduler, WebSocket, lifespan.
"""
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from loguru import logger

from app.config.settings import settings
from app.utils.logger import setup_logger
from app.database.base import create_tables
from app.database.models import *   # noqa — ensures all models are registered
from app.api.market import router as market_router
from app.api.strategies import router as strategy_router
from app.api.trades import trades_router, pnl_router
from app.api.sentiment import router as sentiment_router
from app.websocket.market_ws import websocket_endpoint, broadcast_task
from app.services.strategy_runner import run_strategy_cycle
from app.services.kite_service import kite_service
from app.services.candle_store import candle_store
from app.database.base import AsyncSessionLocal
from app.services import paper_trading_engine as pta

setup_logger()

scheduler = AsyncIOScheduler(timezone="Asia/Kolkata")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──
    logger.info("🚀 Market Engine starting up...")
    await create_tables()

    # Seed all registered strategies into DB
    try:
        from app.strategies.registry import get_registry
        from app.database.models import Strategy
        from sqlalchemy import select
        
        async with AsyncSessionLocal() as db:
            registry = get_registry()
            for s_id, strat in registry.items():
                res = await db.execute(select(Strategy).where(Strategy.id == s_id))
                db_strat = res.scalar_one_or_none()
                if not db_strat:
                    db_strat = Strategy(
                        id=strat.strategy_id,
                        name=strat.name,
                        timeframe=strat.timeframe,
                        description=strat.description,
                        is_active=strat.is_running,
                    )
                    db.add(db_strat)
                else:
                    # Sync running state from memory to db if memory defaults to True
                    if strat.is_running and not db_strat.is_active:
                        db_strat.is_active = True
            await db.commit()
            logger.info("✅ Strategies seeded in DB")
    except Exception as e:
        logger.error(f"Failed to seed strategies: {e}")

    # Set access token from .env if already available
    if settings.kite_access_token:
        kite_service.set_access_token(settings.kite_access_token)
        try:
            profile = await kite_service.get_profile()
            if profile:
                logger.info(f"✅ Zerodha authenticated: {profile.get('user_name', '')}")
        except Exception:
            logger.warning("⚠️  Stored access token may be expired — re-authenticate via /api/market/auth")

    # Schedule strategy runner every 1 minute (Mon-Fri, 9:15-15:25 IST)
    scheduler.add_job(
        run_strategy_cycle,
        "cron",
        day_of_week="mon-fri",
        hour="9-15",
        minute="*/1",
        id="strategy_runner",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("⏰ APScheduler started (strategy runner: every 1 min, market hours)")

    # Start WebSocket broadcast task
    asyncio.create_task(broadcast_task())
    logger.info("📡 WebSocket broadcaster started")

    # Restore active trades from DB
    async with AsyncSessionLocal() as db:
        await pta.load_active_trades(db)

    # Seed candle store in the background so first strategy cycle has full history
    async def _seed_candle_store():
        try:
            from app.services.kite_service import kite_service as _ks
            from app.strategies.registry import TIMEFRAME_MAP
            if not _ks.is_authenticated():
                return
            for tf, kite_interval in [("1minute", "minute"), ("15minute", "15minute")]:
                candles = await _ks.get_nifty_candles(interval=kite_interval, days=2)
                if candles:
                    count = candle_store.upsert_candles(tf, candles)
                    candle_store.mark_initialized(tf)
                    logger.info(f"📦 CandleStore seeded: {tf} with {count} candles")
        except Exception as e:
            logger.warning(f"CandleStore seed failed (will retry on first runner cycle): {e}")

    asyncio.create_task(_seed_candle_store())

    yield

    # ── Shutdown ──
    scheduler.shutdown(wait=False)
    logger.info("👋 Market Engine shutdown complete")


app = FastAPI(
    title="Market Engine API",
    description="Production-ready paper trading platform for Indian equity & derivatives",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url, "http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(market_router)
app.include_router(strategy_router)
app.include_router(trades_router)
app.include_router(pnl_router)
app.include_router(sentiment_router)


# WebSocket endpoint
@app.websocket("/ws")
async def ws_route(websocket: WebSocket):
    await websocket_endpoint(websocket)


@app.get("/health")
async def health():
    return {"status": "ok"}


# ── Serve React frontend build ─────────────────────────────────────────────
_DIST = Path(__file__).parent.parent.parent / "frontend" / "dist"

if _DIST.exists():
    app.mount("/assets", StaticFiles(directory=str(_DIST / "assets")), name="assets")

    @app.get("/")
    async def serve_root():
        return FileResponse(str(_DIST / "index.html"))

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """Catch-all: serve index.html for any unmatched route (SPA fallback)."""
        file_path = _DIST / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(str(file_path))
        return FileResponse(str(_DIST / "index.html"))
else:
    @app.get("/")
    async def root():
        return {
            "app": "Market Engine",
            "version": "1.0.0",
            "status": "running",
            "authenticated": kite_service.is_authenticated(),
            "docs": "/docs",
            "note": "Run 'npm run build' in frontend/ to serve the UI here.",
        }
