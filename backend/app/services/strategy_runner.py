"""
Strategy Runner — APScheduler-driven periodic execution loop.
Fetches live NIFTY candles, runs all active strategies, executes paper trades.
"""
import asyncio
from datetime import datetime, date
from typing import Dict, Any
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.strategies.registry import get_registry, TIMEFRAME_MAP
from app.services.kite_service import kite_service, INSTRUMENT_TOKENS
from app.services import paper_trading_engine as pta
from app.services.pnl_engine import save_pnl_snapshot, compute_live_pnl
from app.services.candle_store import candle_store
from app.utils.indicators import candles_to_dataframe
from app.database.base import AsyncSessionLocal
from app.database.models import Trade, StrategyRun
from app.config.settings import settings

# Cache candles per timeframe to avoid redundant API calls
_candle_cache: Dict[str, Any] = {}


async def _fetch_candles(timeframe: str) -> Any:
    """
    Fetch NIFTY candles for a given timeframe.

    Strategy:
      1. Always attempt to pull fresh candles from Kite (last 2-10 days)
      2. Upsert them into the persistent candle_store
      3. Return the last 200 completed candles from the store

    If the Kite API call fails (network issue, rate limit, etc.),
    the store still holds all prior candles so EMA never goes empty.
    """
    if timeframe != "1minute" and timeframe in _candle_cache:
        return _candle_cache[timeframe]

    kite_interval = TIMEFRAME_MAP.get(timeframe, "5minute")

    if timeframe == "1minute":
        days = 2
    elif timeframe in ("3minute", "5minute"):
        days = 5
    else:
        days = 10

    try:
        candles = await kite_service.get_nifty_candles(interval=kite_interval, days=days)
        if candles:
            # Persist: upsert every completed candle (idempotent, O(1) per candle)
            # The last element from Kite is the partially-formed live candle;
            # we store it anyway and rely on strategy.run() to drop iloc[-1].
            count = candle_store.upsert_candles(timeframe, candles)
            logger.debug(f"[CandleStore] {timeframe}: upserted {len(candles)} candles, total={count}")
    except Exception as e:
        logger.warning(f"[CandleStore] Kite fetch failed for {timeframe}: {e} — using stored candles")

    # Return from the persistent store (graceful fallback if API just failed)
    stored = candle_store.get_candles(timeframe, n=300)
    if not stored:
        # Cold start with no history — this should only happen at first boot before seeding
        logger.warning(f"[CandleStore] No candles for {timeframe} in store — df will be empty this cycle")
        return candles_to_dataframe([])

    df = candles_to_dataframe(stored)

    if timeframe != "1minute":
        _candle_cache[timeframe] = df

    return df


async def run_strategy_cycle():
    """
    Called every minute by APScheduler.
    1. Clear candle cache
    2. Fetch live NIFTY price
    3. Run all registered strategies
    4. Execute paper trades + check SL/target
    5. Save PnL snapshots
    """
    _candle_cache.clear()

    if not kite_service.is_authenticated():
        logger.debug("Kite not authenticated — skipping strategy cycle")
        return

    if not pta.is_market_open():
        logger.debug("Market closed — skipping strategy cycle")
        return

    logger.info("=== Strategy Runner Cycle START ===")

    # Fetch current NIFTY price
    try:
        nifty_quote = await kite_service.get_nifty_quote()
        current_price = float(nifty_quote.get("last_price", 0))
        if not current_price:
            logger.warning("Failed to get NIFTY price; skipping cycle")
            return
    except Exception as e:
        logger.error(f"NIFTY quote error: {e}")
        return

    registry = get_registry()

    async with AsyncSessionLocal() as db:
        for strategy_id, strategy in registry.items():
            if not strategy.is_running:
                continue

            try:
                # Find the current price for the active trade to update PnL
                trade_price = current_price
                if pta.has_active_trade(strategy_id):
                    trade = pta.get_active_trade(strategy_id)
                    trade_sym = trade.get("symbol", "NIFTY 50")
                    if "STRADDLE" in trade_sym:
                        # signal_data may be double-nested: trade['signal_data']['signal_data']
                        sig_data = trade.get("signal_data") or {}
                        inner = sig_data.get("signal_data") or sig_data   # unwrap if nested
                        sell_leg = inner.get("sell_leg", {})
                        buy_leg = inner.get("buy_leg", {})
                        if sell_leg.get("symbol") and buy_leg.get("symbol"):
                            try:
                                q = await kite_service.get_quote([sell_leg["symbol"], buy_leg["symbol"]])
                                ce_price = float(q.get(sell_leg["symbol"], {}).get("last_price") or sell_leg.get("price", 0))
                                pe_price = float(q.get(buy_leg["symbol"], {}).get("last_price") or buy_leg.get("price", 0))
                                if ce_price > 0 and pe_price > 0:
                                    trade_price = ce_price + pe_price
                                    logger.debug(f"[{strategy_id}] Straddle live price: CE={ce_price} + PE={pe_price} = {trade_price}")
                                else:
                                    logger.warning(f"[{strategy_id}] Straddle quote returned zero price. CE={ce_price} PE={pe_price}. Skipping MTM check.")
                                    trade_price = None  # Sentinel: skip MTM check this cycle
                            except Exception as eq:
                                logger.warning(f"[{strategy_id}] Failed to get straddle quotes: {eq}. Skipping MTM check.")
                                trade_price = None  # Sentinel: skip MTM check this cycle
                        else:
                            logger.warning(f"[{strategy_id}] sell_leg/buy_leg symbols missing. Skipping MTM check.")
                            trade_price = None  # Sentinel: skip MTM check this cycle
                    elif "NFO" in trade_sym:
                        # Fetch live option quote (sell leg for spreads)
                        q = await kite_service.get_quote([trade_sym])
                        opt = q.get(trade_sym, {})
                        trade_price = float(opt.get("last_price", trade.get("entry_price")))

                # ── Expiry Day Auto-Square Off (15:25) ──────────
                if pta.has_active_trade(strategy_id):
                    active_trade = pta.get_active_trade(strategy_id)
                    trade_sym = active_trade.get("symbol", "")
                    
                    # Resolve true symbol for multi-leg strategies (unwrap nested signal_data)
                    sig_data = active_trade.get("signal_data") or {}
                    inner = sig_data.get("signal_data") or sig_data
                    sell_leg = inner.get("sell_leg", {})
                    base_sym = sell_leg.get("symbol") if sell_leg else trade_sym
                    
                    if base_sym:
                        dt = datetime.now()
                        trade_expiry = kite_service.get_expiry_for_symbol(base_sym)
                        
                        # If today is expiry day, square off at 15:25
                        if trade_expiry and trade_expiry == date.today():
                            if dt.hour == 15 and dt.minute >= 25:
                                logger.info(f"[{strategy_id}] Expiry Day Auto-Square Off triggered at 15:25 for {base_sym}")
                                exit_info = await pta.exit_trade(
                                    db, strategy_id, trade_price, reason="EXPIRY_AUTO_SQUARE_OFF"
                                )
                                if exit_info:
                                    strategy.notify_exit("EXPIRY_AUTO_SQUARE_OFF")
                                    await _recalc_spread_pnl(db, exit_info)

                # Check if existing trade hit SL/target or universal MTM loss limit
                exit_info = await pta.tick_check(db, strategy_id, trade_price)
                if exit_info:
                    # Notify strategy of exit outcome (state machine update)
                    strategy.notify_exit(exit_info.get("status", "STRATEGY_EXIT"))
                    # Recalculate spread or straddle PnL (both have two legs)
                    await _recalc_spread_pnl(db, exit_info)

                # ── Cross-Strategy Universal MTM Stop (Straddle 2A) ──────────────
                # trade_price = None means straddle quote fetch failed — skip check this cycle
                if not pta.has_active_trade(strategy_id) or trade_price is None:
                    pass  # already exited or straddle price unavailable — skip MTM
                elif hasattr(strategy, "MAX_LOSS_PCT") and pta.has_active_trade(strategy_id):
                    active = pta.get_active_trade(strategy_id)
                    cap = getattr(strategy, "fund_required", 300000)
                    entry_p = float(active.get("entry_price", 0))
                    direction = active.get("direction", "SELL")
                    qty = int(active.get("quantity", 50))
                    if direction == "SELL":
                        live_pnl = (entry_p - trade_price) * qty
                    else:
                        live_pnl = (trade_price - entry_p) * qty
                    if live_pnl <= cap * strategy.MAX_LOSS_PCT:
                        logger.error(
                            f"[{strategy_id}] MTM Loss limit hit: live PnL=₹{live_pnl:.2f} "
                            f"(entry={entry_p} trade_price={trade_price:.2f} cap={cap} "
                            f"threshold={cap * strategy.MAX_LOSS_PCT:.2f}). Forcing exit."
                        )
                        e_info = await pta.exit_trade(db, strategy_id, trade_price, reason="UNIVERSAL_EXIT")
                        if e_info:
                            strategy.notify_exit("UNIVERSAL_EXIT")
                            await _recalc_spread_pnl(db, e_info)


                df = await _fetch_candles(strategy.timeframe)
                if df.empty:
                    continue

                # Debugging EMA 21 Lag
                if strategy_id == "ema_21_option_selling":
                    try:
                        from app.utils.indicators import ema
                        import json
                        df_debug = df.copy()
                        df_debug["ema21"] = ema(df_debug["close"], 21)
                        if len(df_debug) >= 2:
                            r1 = df_debug.iloc[-1]
                            r2 = df_debug.iloc[-2]
                            with open("ema_debug.txt", "a") as f:
                                f.write(f"\n[EMA21-DEBUG] RUNNER EVALUATING DF (Length: {len(df_debug)}):\n")
                                f.write(f"  ILOC[-1] Form: {r1['date']} | C: {r1.get('close', 0)} | E: {r1.get('ema21', 0)}\n")
                                f.write(f"  ILOC[-2] Comp: {r2['date']} | C: {r2.get('close', 0)} | E: {r2.get('ema21', 0)}\n")
                    except Exception as e:
                        with open("ema_debug.txt", "a") as f:
                            f.write(f"\n[EMA21-DEBUG] Crash: {e}\n")

                signal = strategy.run(df)

                # ── EMA 9 Crossover Debug ────────────────────────────────────
                if strategy_id == "ema_9_crossover_option_selling":
                    try:
                        from app.utils.indicators import ema as _ema
                        _df = df.copy()
                        _df["ema9"] = _ema(_df["close"], 9)
                        completed = _df.iloc[:-1]   # drop forming candle
                        if len(completed) >= 2:
                            prev = completed.iloc[-2]
                            cur  = completed.iloc[-1]
                            p_close, p_ema = float(prev["close"]), float(prev["ema9"])
                            c_close, c_ema = float(cur["close"]),  float(cur["ema9"])
                            bull = (p_ema <= p_close) and (c_ema > c_close)
                            bear = (p_ema >= p_close) and (c_ema < c_close)
                            logger.info(
                                f"[EMA9-DBG] df={len(df)} rows | "
                                f"prev [{prev.get('date','')}]: C={p_close:.2f} E={p_ema:.2f} above={p_ema>p_close} | "
                                f"cur  [{cur.get('date','')}]: C={c_close:.2f} E={c_ema:.2f} above={c_ema>c_close} | "
                                f"bull={bull} bear={bear} signal={signal}"
                            )
                    except Exception as _e:
                        logger.warning(f"[EMA9-DBG] Crash: {_e}")

                # Log run
                run = StrategyRun(
                    strategy_id=strategy_id,
                    signal=signal["signal"] if signal else "NONE",
                    price=current_price,
                    candle_data={"candles": len(df)},
                )
                db.add(run)

                # ── Spread signal (SELL_SPREAD): dual-leg resolution ──────────
                if signal and signal.get("signal") == "SELL_SPREAD":
                    signal = await _resolve_spread_legs(signal, strategy, current_price)

                # ── Straddle signal (SELL_STRADDLE): dual-leg resolution ──────────
                if signal and signal.get("signal") == "SELL_STRADDLE":
                    signal = await _resolve_straddle_legs(signal, strategy, current_price)
                    # Only force-exit an existing trade on a genuine RE-ENTRY signal,
                    # not on INITIAL_ENTRY (which can happen after a backend restart
                    # if strategy state resets but the DB trade is still active).
                    is_reentry = signal and signal.get("reason") == "REENTRY"
                    if is_reentry and pta.has_active_trade(strategy_id):
                        logger.warning(f"[{strategy_id}] Force closing existing straddle for re-entry.")
                        # ⚠️ Use trade_price (combined premium), NOT current_price (NIFTY spot)
                        reentry_exit_price = trade_price if trade_price else signal.get("price", current_price)
                        exit_info = await pta.exit_trade(db, strategy_id, reentry_exit_price, reason="REENTRY_EXIT")
                        if exit_info:
                            strategy.notify_exit("REENTRY_EXIT")
                            await _recalc_spread_pnl(db, exit_info)


                # ── Forced reversal exit for spread regime change ─────────────
                if pta.has_active_trade(strategy_id) and signal:
                    active_trade = pta.get_active_trade(strategy_id)
                    direction    = active_trade["direction"]
                    sig_dir      = signal.get("signal")
                    spread_meta  = active_trade.get("signal_data", {}) or {}

                    # Detect regime reversal for credit spreads
                    active_regime = spread_meta.get("regime")
                    new_regime    = signal.get("regime")
                    regime_flip   = (
                        active_regime and new_regime
                        and active_regime != new_regime
                        and signal.get("spread_type")  # it's a spread signal
                    )

                    if regime_flip:
                        logger.info(
                            f"[{strategy_id}] Regime reversal: {active_regime} → {new_regime}."
                            f" Forcing exit at sell-leg price ₹{trade_price:.2f}."
                        )
                        exit_info = await pta.exit_trade(
                            db, strategy_id, trade_price, reason="REVERSAL_EXIT"
                        )
                        if exit_info:
                            strategy.notify_exit("REVERSAL_EXIT")
                            await _recalc_spread_pnl(db, exit_info)
                        # Clear so the reversal entry can be placed below

                    elif "option_type" in signal:
                        # Existing single-leg SAR logic
                        opt_type   = signal["option_type"]
                        active_sym = active_trade.get("symbol", "")
                        if (opt_type == "PE" and "CE" in active_sym) or \
                           (opt_type == "CE" and "PE" in active_sym):
                            sig_dir = "EXIT"

                        if sig_dir == "EXIT" or (sig_dir == "BUY" and direction == "SELL") or \
                                                 (sig_dir == "SELL" and direction == "BUY"):
                            logger.info(f"[{strategy_id}] Dynamic Exit Triggered: {sig_dir} / {direction}")
                            exit_info = await pta.exit_trade(
                                db, strategy_id, trade_price, reason="STRATEGY_EXIT"
                            )
                            if exit_info:
                                strategy.notify_exit("STRATEGY_EXIT")
                                await _recalc_spread_pnl(db, exit_info)
                            sig_dir = signal.get("signal")

                # Allow new entry if no active trade and signal is ready
                if not pta.has_active_trade(strategy_id) and signal and signal.get("signal") in ("BUY", "SELL"):
                    # Resolve Option Symbol if strategy uses it (single-leg fallback)
                    if "option_type" in signal:
                        opt_data = await kite_service.get_atm_option_quote(current_price, signal["option_type"])
                        if opt_data and opt_data.get("price"):
                            signal["symbol"] = opt_data["symbol"]
                            signal["price"]  = opt_data["price"]
                            logger.info(f"[{strategy_id}] Resolved ATM Option: {opt_data['symbol']} @ {opt_data['price']}")
                        else:
                            atm = round(current_price / 50) * 50
                            signal["symbol"] = f"NFO:NIFTY {atm} {signal['option_type']}"
                            logger.warning(f"[{strategy_id}] Failed to get Option quote, fallback")

                    logger.info(f"[{strategy_id}] Signal: {signal['signal']} @ {signal.get('symbol', 'NIFTY 50')} | {signal['price']}")
                    await pta.execute_paper_trade(db, strategy_id, signal)

            except Exception as e:
                logger.error(f"Error in strategy [{strategy_id}]: {e}")
                import traceback
                logger.debug(traceback.format_exc())

        await db.commit()

    logger.info("=== Strategy Runner Cycle END ===")


# ── Spread Helper Functions ───────────────────────────────────────────────────

async def _resolve_spread_legs(
    signal: Dict[str, Any],
    strategy,
    current_price: float,
) -> Dict[str, Any]:
    """
    For a SELL_SPREAD signal:
      1. Find the sell leg option (closest LTP to ~₹125)
      2. Find the buy leg option (closest LTP to ~₹25, further OTM than sell leg)
      3. Normalize signal dict for paper_trading_engine
    Returns the updated signal dict (or unchanged if leg resolution fails).
    """
    sell_type  = signal.get("sell_option_type", "PE")
    buy_type   = signal.get("buy_option_type",  "PE")
    sell_tgt   = signal.get("sell_target_premium", 125)
    buy_tgt    = signal.get("buy_target_premium",   25)

    expiry = kite_service.get_expiry_for_trade()

    # Sell leg: scan from ATM outward
    sell_leg = await kite_service.find_option_by_premium(
        spot_price=current_price,
        opt_type=sell_type,
        target_premium=sell_tgt,
        expiry=expiry,
        min_otm_distance=0,
    )

    if not sell_leg or not sell_leg.get("price"):
        logger.warning(f"[{strategy.strategy_id}] Spread entry aborted: sell leg not found")
        return {}  # empty → runner skips entry

    # Buy leg: scan starts 4 strikes further OTM than where the sell leg landed
    sell_otm_dist = int(abs(sell_leg["strike"] - round(current_price / 50) * 50) // 50)
    buy_start_dist = sell_otm_dist + 4   # hedge is further OTM
    buy_leg = await kite_service.find_option_by_premium(
        spot_price=current_price,
        opt_type=buy_type,
        target_premium=buy_tgt,
        expiry=expiry,
        min_otm_distance=int(max(buy_start_dist, 4)),
    )

    if not buy_leg or not buy_leg.get("price"):
        logger.warning(f"[{strategy.strategy_id}] Spread entry: buy-leg not found — using sell-leg only")
        buy_leg = {"symbol": None, "price": 0, "strike": None}

    sell_price = sell_leg["price"]
    buy_price  = buy_leg["price"]

    # Build normalized signal for paper_trading_engine
    signal["signal"]      = "SELL"          # direction on the sell leg
    signal["symbol"]      = sell_leg["symbol"]
    signal["price"]       = sell_price       # sell leg entry premium (monitored)
    signal["sl"]          = round(sell_price * 1.5,  2)   # 50% increase in sell-leg premium
    signal["target"]      = round(sell_price * 0.30, 2)   # 70% decay in sell-leg premium
    signal["signal_data"] = {
        "spread_type":  signal.get("spread_type"),
        "regime":       signal.get("regime"),
        "entry_reason": signal.get("entry_reason"),
        "sell_leg": {
            "symbol": sell_leg["symbol"],
            "price":  sell_price,
            "strike": sell_leg["strike"],
        },
        "buy_leg": {
            "symbol": buy_leg["symbol"],
            "price":  buy_price,
            "strike": buy_leg["strike"],
        },
        "net_credit": round(sell_price - buy_price, 2),
    }

    logger.info(
        f"[{strategy.strategy_id}] Spread resolved: "
        f"SELL {sell_leg['symbol']} @₹{sell_price:.2f} | "
        f"BUY {buy_leg['symbol']} @₹{buy_price:.2f} | "
        f"net_credit=₹{sell_price - buy_price:.2f} | "
        f"SL=₹{signal['sl']:.2f} | target=₹{signal['target']:.2f}"
    )
    return signal

async def _resolve_straddle_legs(
    signal: Dict[str, Any],
    strategy,
    current_price: float,
) -> Dict[str, Any]:
    """
    For a SELL_STRADDLE signal:
      1. Find the ATM CE and PE options
      2. Calculate N based on Expiry (DTE)
      3. Compute exit distance = combined_premium / N
      4. Normalize signal dict for paper_trading_engine
    """
    expiry = kite_service.get_expiry_for_trade()
    if not expiry:
        logger.warning(f"[{strategy.strategy_id}] Cannot resolve straddle: no expiry found")
        return {}
        
    straddle = await kite_service.get_straddle_quotes(current_price, expiry)
    if not straddle or not straddle.get("combined_premium"):
        logger.warning(f"[{strategy.strategy_id}] Straddle entry aborted: quotes not found")
        return {}
        
    comb_premium = straddle["combined_premium"]
    ce_leg = straddle["ce"]
    pe_leg = straddle["pe"]

    # Calculate DTE (Days to Expiry)
    dte = (expiry - date.today()).days
    N = 2 if dte in (0, 1) else 3
    exit_distance = round(comb_premium / N, 2)
    
    # We pass the real strike and premium back to the strategy so it correctly maps re-entry bounds
    strategy.update_internal_state(straddle["strike"], comb_premium)

    # Normalize signal
    # Even though it's technically two legs, paper engine tracks 'sell_price' as the comb_premium 
    # to maintain MTM correctness for shorts, but the actual calculation works identical to spreads.
    # Therefore, we treat entry_price = comb_premium and direction = SELL.
    signal["signal"] = "SELL" 
    signal["symbol"] = f"STRADDLE NIFTY {straddle['strike']} {expiry}"
    signal["price"]  = comb_premium
    signal["sl"]     = None
    signal["target"] = None
    
    # Store complete metadata 
    signal["signal_data"] = {
        "signal": "SELL_STRADDLE",
        "entry_reason": signal.get("entry_reason"),
        "spot_price": current_price,
        "spot_exit_distance": exit_distance,
        "combined_premium": comb_premium,
        "strike": straddle["strike"],
        "expiry": str(expiry),
        "sell_leg": {
            "symbol": ce_leg["symbol"],
            "price":  ce_leg["price"],
            "strike": straddle["strike"],
        },
        "buy_leg": {
            # In a straddle, both legs are sold, but we abuse "buy_leg" in _recalc_spread_pnl
            # to mean "the other leg". WAIT: if we map PE to buy_leg, _recalc_spread_pnl will treat it as a long leg.
            # We must fix PnL logic OR treat them both dynamically. 
            "symbol": pe_leg["symbol"],
            "price": pe_leg["price"], 
            "strike": straddle["strike"],
            "direction": "SELL"
        }
    }
    
    # Custom flag so _recalc_spread_pnl knows this is a straddle (both short)
    signal["signal_data"]["is_straddle"] = True
    
    logger.info(
        f"[{strategy.strategy_id}] Straddle resolved: "
        f"CE {ce_leg['symbol']} @₹{ce_leg['price']:.2f} | "
        f"PE {pe_leg['symbol']} @₹{pe_leg['price']:.2f} | "
        f"Comb Prem=₹{comb_premium:.2f} | spot={current_price:.2f} | N={N} | limit=±{exit_distance:.2f}"
    )
    return signal


async def _recalc_spread_pnl(db: AsyncSession, exit_info: Dict[str, Any]) -> None:
    """
    After a spread trade closes, recalculate the PnL using both legs.

    Spread PnL = (sell_entry - sell_exit) * qty - (buy_exit - buy_entry) * qty

    If the buy leg data is missing (non-spread trade), this is a no-op.
    """
    spread_meta = (exit_info.get("signal_data") or {})
    buy_leg = spread_meta.get("buy_leg", {}) if isinstance(spread_meta, dict) else {}
    sell_leg = spread_meta.get("sell_leg", {}) if isinstance(spread_meta, dict) else {}

    if not buy_leg or not buy_leg.get("symbol"):
        return   # not a spread trade, nothing to patch

    buy_sym   = buy_leg["symbol"]
    buy_entry = float(buy_leg.get("price", 0))
    sell_entry = float(sell_leg.get("price", exit_info.get("entry_price", 0)))
    sell_exit  = float(exit_info.get("exit_price", sell_entry))
    qty        = int(exit_info.get("quantity", 75))

    try:
        buy_quotes = await kite_service.get_quote([buy_sym])
        buy_exit   = float(buy_quotes.get(buy_sym, {}).get("last_price", buy_entry))
    except Exception as e:
        logger.warning(f"_recalc_spread_pnl: failed to fetch second-leg LTP: {e}")
        buy_exit = buy_entry  # neutral fallback

    is_straddle = spread_meta.get("is_straddle", False)
    
    if is_straddle:
        # Straddle: both legs are sold.
        # PnL = (entry1 - exit1) + (entry2 - exit2)
        spread_pnl = round(
            ((sell_entry - sell_exit) + (buy_entry - buy_exit)) * qty, 2
        )
    else:
        # Spread: sell_leg is short, buy_leg is long.
        # PnL = (entry1 - exit1) - (entry2 - exit2) OR (entry1 - exit1) + (exit2 - entry2)
        spread_pnl = round(
            (sell_entry - sell_exit) * qty + (buy_exit - buy_entry) * qty, 2
        )

    # Patch the DB row with the correct spread PnL
    try:
        from sqlalchemy import update
        from app.database.models import Trade
        trade_id = exit_info.get("id")
        if trade_id:
            await db.execute(
                update(Trade).where(Trade.id == trade_id).values(pnl=spread_pnl)
            )
            await db.commit()
            logger.info(
                f"Spread PnL recalculated: sell={sell_entry}→{sell_exit}, "
                f"buy={buy_entry}→{buy_exit}, net PnL=₹{spread_pnl} qty={qty}"
            )
    except Exception as e:
        logger.warning(f"_recalc_spread_pnl: DB patch failed: {e}")
