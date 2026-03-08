"""
Straddle 2A (Vanilla) — Intraday NIFTY ATM Short Straddle
==========================================================
Rules (from spec):
1.  Instrument  : NIFTY — intraday, option selling
2.  Strike      : ATM at entry
3.  Entry       : 9:21 AM (first 1-min bar at or after 9:21)
4.  Note        : entry combined_premium and entry spot price
5.  Universal exit: 3:00 PM sharp, OR 1% loss of deployed capital
"""

from datetime import datetime, time, date, timedelta
from typing import Optional, Dict, Any
import pandas as pd
from loguru import logger

from app.strategies.base_strategy import BaseStrategy


class Straddle2AVanilla(BaseStrategy):

    strategy_id = "straddle_2a_vanilla"
    name        = "Straddle 2A (Vanilla)"
    timeframe   = "1minute"

    fund_required = 220_000.0
    lot_size      = 65
    MAX_LOSS_PCT  = -0.01          # -1% of deployed capital

    ENTRY_TIME = time(9, 39)       # Scheduled start at 9:39 AM
    EXIT_TIME  = time(15, 0)       # universal exit (spec rule 11)

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def __init__(self):
        super().__init__()
        self.reset_day()

    def reset_day(self):
        """Called at start of each new trading day."""
        self._current_date        = None
        self._active_trade        = False
        self._lock_for_day        = False

        # State recorded at entry (needed for movement exit & re-entry check)
        self._entry_spot          = None   # NIFTY spot at entry
        self._prev_strike         = None   # ATM strike of previous straddle
        self._combined_premium    = None   # combined premium of active straddle
        self._combined_premium    = None   # combined premium of active straddle

    def _new_day_check(self, dt: datetime):
        d = dt.date()
        if self._current_date != d:
            self.reset_day()
            self._current_date = d

    # ── Main signal generator ──────────────────────────────────────────────────

    def run(self, df: pd.DataFrame) -> Optional[Dict[str, Any]]:
        if len(df) < 2:
            return None

        # Use last COMPLETED bar (iloc[-2]); iloc[-1] is the forming bar
        bar  = df.iloc[-2]
        dt = bar["date"]
        
        # Ensure dt is a datetime object
        if isinstance(dt, str):
            dt = datetime.fromisoformat(dt)
            
        # Shift dt to the END of the 1-minute candle so that 9:20 candle close is evaluated exactly at 9:21
        dt = dt + timedelta(minutes=1)
        
        spot = float(bar["close"])

        self._new_day_check(dt)

        # ── Stale bar guard: if the last completed bar is from a previous day,
        #    the CandleStore doesn't have today's candles yet — skip silently.
        #    Do NOT treat yesterday's 15:29 bar as today's EOD.
        from datetime import date as _date
        import pytz
        today = datetime.now(pytz.timezone("Asia/Kolkata")).date()
        if dt.date() < today:
            return None

        if self._lock_for_day:
            return None

        # ── Universal Exit: 3:00 PM ────────────────────────────────────────────
        if dt.time() >= self.EXIT_TIME:
            self._lock_for_day = True
            if self._active_trade:
                logger.info(f"[{self.strategy_id}] Universal exit at 15:00 (EOD)")
                return {"signal": "EXIT_ALL", "reason": "EOD"}
            return None

        t    = dt.time()
        atm  = round(spot / 50) * 50   # nearest 50-point ATM strike

        # ── Initial Entry at 9:21 AM ───────────────────────────────────────────
        # Spec: "Start at 9:21 am" — enter on the FIRST bar at/after 9:21 AM
        if not self._active_trade and not self._lock_for_day and t >= self.ENTRY_TIME:
            # Only enter on the very first eligible bar (set _active_trade immediately)
            if self._prev_strike is None:
                logger.info(f"[{self.strategy_id}] Initial SELL_STRADDLE entry at {t}, spot={spot}, ATM={atm}")
                self._active_trade = True
                self._entry_spot   = spot
                self._prev_strike  = atm
                return self._signal("INITIAL_ENTRY", atm, spot)

        # ── Re-entry Check ─────────────────────────────────────────────────────
        # Note: Vanilla strategy usually doesn't re-enter after MTM SL,
        # but the check remains for safety if _active_trade=False.
        if (
            not self._active_trade
            and self._prev_strike is not None
            and self._combined_premium is not None
            and t >= self.ENTRY_TIME
            and t < self.EXIT_TIME
            and dt.minute % 3 == 0   # multiples of 3 (9:21→9:24→9:27…)
        ):
            upper = self._prev_strike + self._combined_premium
            lower = self._prev_strike - self._combined_premium

            if atm > upper or atm <= lower:
                logger.info(
                    f"[{self.strategy_id}] Re-entry: ATM={atm} (prev_strike={self._prev_strike}, "
                    f"premium={self._combined_premium:.2f}, upper={upper:.2f}, lower={lower:.2f})"
                )
                self._active_trade = True
                self._entry_spot   = spot
                self._prev_strike  = atm
                return self._signal("REENTRY", atm, spot)

        return None

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _signal(self, reason: str, strike: int, spot: float) -> Dict[str, Any]:
        return {
            "signal":          "SELL_STRADDLE",
            "reason":          reason,
            "expected_strike": strike,
            "spot_price":      spot,
            "option_types":    ["CE", "PE"],
        }

    def update_internal_state(self, strike: int, combined_premium: float):
        """
        Called by the strategy_runner AFTER straddle legs are resolved.
        Signature matches the runner call:
            strategy.update_internal_state(straddle["strike"], comb_premium)

        Sets the movement_threshold = combined_premium / N
        where N = 2 for 0/1 DTE, N = 3 for other days.
        """
        from datetime import date as date_type
        # Determine DTE — look at today's weekly expiry (Thursday)
        today = date_type.today()
        days_to_thursday = (3 - today.weekday()) % 7  # 0 on Thursday, 1 on Wed, etc.
        dte = days_to_thursday

        N = 2 if dte <= 1 else 3
        self._combined_premium   = float(combined_premium)
        # Also update strike (may have changed on re-entry)
        self._prev_strike = strike

        logger.info(
            f"[{self.strategy_id}] Internal state updated: strike={strike}, "
            f"premium={combined_premium:.2f}, DTE={dte}, N={N}"
        )

    def notify_exit(self, reason: str, mtm_pct: float = None):
        """
        Called by the runner after a trade is closed.
        Reset active flag; lock for day only on universal exit or MTM loss.
        """
        self._active_trade = False
        self._entry_spot   = None   # reset for next re-entry measurement

        if reason in ("UNIVERSAL_EXIT", "EOD") or (mtm_pct and mtm_pct <= self.MAX_LOSS_PCT):
            self._lock_for_day = True
            logger.info(f"[{self.strategy_id}] Day locked after {reason}")
        else:
            logger.info(f"[{self.strategy_id}] Exited ({reason}), awaiting re-entry signal")
