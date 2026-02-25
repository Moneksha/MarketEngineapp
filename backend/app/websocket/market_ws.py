"""
WebSocket broadcaster — streams live market data to all connected clients.
Broadcasts every 1 second: NIFTY price, heavyweights, strategy PnL.
"""
import asyncio
import json
from datetime import datetime
from typing import Set
from fastapi import WebSocket, WebSocketDisconnect
from loguru import logger

from app.services.kite_service import kite_service
from app.database.base import AsyncSessionLocal
from app.services.pnl_engine import compute_live_pnl
from app.strategies.registry import get_registry

connected_clients: Set[WebSocket] = set()


async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.add(websocket)
    logger.info(f"WS client connected. Total: {len(connected_clients)}")
    try:
        while True:
            try:
                # Wait for any client message (ping/pong/close) with a long timeout.
                # This keeps the connection alive without requiring the client to send anything.
                msg = await asyncio.wait_for(websocket.receive(), timeout=30)
                if msg.get("type") == "websocket.disconnect":
                    break
            except asyncio.TimeoutError:
                # No message from client in 30s — that's fine, just keep waiting
                continue
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.warning(f"WS error: {e}")
    finally:
        connected_clients.discard(websocket)
        logger.info(f"WS client disconnected. Total: {len(connected_clients)}")


_last_payload: dict = {}
_payload_lock = asyncio.Lock()


async def broadcast_task():
    """Background task: build payload every 1 second and push to all clients."""
    global _last_payload
    while True:
        await asyncio.sleep(1)
        try:
            # Build payload with a hard 8-second timeout so slow Kite API
            # calls never block WS sends indefinitely
            async with _payload_lock:
                payload = await asyncio.wait_for(_build_payload(), timeout=8)
                _last_payload = payload

            msg = json.dumps(payload, default=str)
            dead = set()
            for ws in connected_clients.copy():
                try:
                    await asyncio.wait_for(ws.send_text(msg), timeout=2)
                except Exception:
                    dead.add(ws)
            connected_clients.difference_update(dead)
        except asyncio.TimeoutError:
            logger.warning("Broadcast payload build timed out — skipping cycle")
        except Exception as e:
            logger.error(f"Broadcast error: {e}")


async def _build_payload() -> dict:
    """Assemble market snapshot. Runs fast parallel Kite calls."""
    payload: dict = {
        "type": "market_update",
        "timestamp": datetime.now().isoformat(),
        "authenticated": kite_service.is_authenticated(),
    }

    if not kite_service.is_authenticated():
        payload["nifty"] = None
        payload["heavyweights"] = []
        payload["strategies"] = []
        payload["options"] = {}
        return payload

    current_price = 0

    # ── Fetch NIFTY + heavyweights + VIX in parallel ────────────────────────
    try:
        nifty_task = asyncio.create_task(kite_service.get_nifty_quote())
        hw_task    = asyncio.create_task(kite_service.get_heavyweight_quotes())
        vix_task   = asyncio.create_task(kite_service.get_vix_quote())

        nifty_quote, hw, vix = await asyncio.gather(
            nifty_task, hw_task, vix_task, return_exceptions=True
        )

        if isinstance(nifty_quote, Exception) or not nifty_quote:
            payload["nifty"] = None
        else:
            current_price = float(nifty_quote.get("last_price", 0))
            ohlc_close    = nifty_quote.get("ohlc", {}).get("close", 0)
            net_change    = float(nifty_quote.get("net_change", 0))
            change_pct    = (net_change / ohlc_close * 100) if ohlc_close else 0
            payload["nifty"] = {
                "ltp":        current_price,
                "change":     round(float(nifty_quote.get("change", 0) or net_change), 2),
                "change_pct": round(change_pct, 2),
            }

        payload["heavyweights"] = list(hw.values()) if isinstance(hw, dict) else []
        payload["vix"] = vix if isinstance(vix, dict) else {"ltp": 0, "change": 0, "change_pct": 0}

    except Exception as e:
        logger.error(f"Quote fetch error: {e}")
        payload["nifty"] = None
        payload["heavyweights"] = []

    # ── Options data (best-effort, skip if slow) ─────────────────────────────
    try:
        payload["options"] = await asyncio.wait_for(
            kite_service.get_options_data(), timeout=4
        )
    except Exception:
        payload["options"] = {}

    # ── Strategy PnL ──────────────────────────────────────────────────────────
    strategy_pnls = []
    registry = get_registry()
    try:
        from app.services import paper_trading_engine as pta
        async with AsyncSessionLocal() as db:
            for sid in registry:
                try:
                    # For straddle strategies, use combined CE+PE premium, not NIFTY spot
                    strategy_price = current_price
                    active_trade = pta.get_active_trade(sid)
                    if active_trade:
                        trade_sym = active_trade.get("symbol", "")
                        if "STRADDLE" in trade_sym:
                            sig_data = active_trade.get("signal_data") or {}
                            inner = sig_data.get("signal_data") or sig_data  # unwrap nested
                            sell_leg = inner.get("sell_leg", {})
                            buy_leg  = inner.get("buy_leg", {})
                            if sell_leg.get("symbol") and buy_leg.get("symbol"):
                                try:
                                    q = await kite_service.get_quote([sell_leg["symbol"], buy_leg["symbol"]])
                                    ce_p = float(q.get(sell_leg["symbol"], {}).get("last_price") or sell_leg.get("price", 0))
                                    pe_p = float(q.get(buy_leg["symbol"],  {}).get("last_price") or buy_leg.get("price", 0))
                                    if ce_p > 0 and pe_p > 0:
                                        strategy_price = ce_p + pe_p
                                except Exception:
                                    pass  # fall back to NIFTY spot gracefully

                    pnl = await compute_live_pnl(db, sid, strategy_price)
                    strategy_pnls.append({
                        "strategy_id":    sid,
                        "is_running":     registry[sid].is_running,
                        "total_equity":   pnl["total_equity"],
                        "roi":            pnl.get("roi", 0.0),
                        "realized_pnl":   pnl["realized_pnl"],
                        "unrealized_pnl": pnl["unrealized_pnl"],
                        "trade_count":    pnl["trade_count"],
                        "active_trade":   pnl.get("active_trade"),
                    })
                except Exception as e:
                    logger.warning(f"Strategy PnL build error for {sid}: {e}")
    except Exception as e:
        logger.warning(f"Global PnL build error: {e}")
    payload["strategies"] = strategy_pnls


    return payload
