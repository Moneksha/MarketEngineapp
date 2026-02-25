"""
Intraday ATM Short Straddle (Straddle 2A Vanilla)
==================================================================
Instrument: NIFTY
Strategy Type: Intraday Option Selling
Structure: ATM Short Straddle (Sell CE + Sell PE)
Execution Style: Rule-based, systematic
Timeframe: 1minute (evaluated every minute)
Entry Time: Strictly at 09:21 AM
Exit Logic: Movement-based exit. Exit if spot moves by (Combined Premium / N)
            N = 2 if 0 DTE or 1 DTE; N = 3 otherwise.
Re-Entry Logic:
   - Time must be a multiple of 3 minutes (e.g., 09:24, 09:27)
   - ATM strike must be > last_strike + combined_premium 
     OR <= last_strike - combined_premium
Universal Rules: Hard stop if Time >= 15:00 OR MTM loss >= 1% of capital. No further trades allowed.
"""
from datetime import datetime
from typing import Optional, Dict, Any
import pandas as pd
from loguru import logger

from app.strategies.base_strategy import BaseStrategy


class Straddle2AVanilla(BaseStrategy):
    # ── Identity ──────────────────────────────────────────────────────────────
    strategy_id     = "straddle_2a_vanilla"
    name            = "Straddle 2A (Vanilla)"
    description     = (
        "[1min] Intraday ATM Short Straddle (CE+PE) on NIFTY weekly options. "
        "Initial entry at exactly 09:21 AM. "
        
    )
    timeframe       = "1minute"
    indicators_used = []  # Purely price-action / premium based
    entry_rules     = (
        "Initial Entry: Time == 09:21 AM. "
        
    )
    exit_rules      = (
        ""
    )
    sl_logic        = "Max -1% of total capital MTM drawdown."
    target_logic    = "None (pure trend-following exit via spot movement boundaries)."
    fund_required   = 220_000.0  # margin for one NIFTY short straddle (approx 1.5L per leg assuming hedge/margin benefits)
    lot_size        = 65          # current NIFTY lot size

    # Universal hard-stop rules
    MAX_LOSS_PCT    = -0.01       # -1% of fund_required

    def __init__(self):
        super().__init__()
        # ── Internal State Machine ──
        # State resetting occurs automatically at the start of a new trading session.
        self._current_date: Optional[str] = None
        
        self._has_traded_today: bool = False
        self._universal_exit_triggered: bool = False
        self._last_straddle_strike: Optional[int] = None
        self._last_combined_premium: Optional[float] = None
        
        self.start()

    def _check_and_reset_daily_state(self, current_dt: datetime) -> None:
        """Reset state if it's a new calendar day."""
        dt_str = current_dt.strftime("%Y-%m-%d")
        if self._current_date != dt_str:
            self._current_date = dt_str
            self._has_traded_today = False
            self._universal_exit_triggered = False
            self._last_straddle_strike = None
            self._last_combined_premium = None

    def run(self, df: pd.DataFrame) -> Optional[Dict[str, Any]]:
        """
        Evaluate logic on the last completed 1-minute candle.
        Since runner calls every minute, we check the latest closed candle 
        to see if the time matches our rules.
        """
        if df.empty or len(df) < 2:
            return None

        # df.iloc[-1] is forming, df.iloc[-2] is the last completed candle
        cur = df.iloc[-2]
        close_price = float(cur["close"])
        dt: datetime = cur["date"] if isinstance(cur.get("date"), datetime) else datetime.now()

        self._check_and_reset_daily_state(dt)

        if self._universal_exit_triggered:
            # Cannot trade anymore today
            return None

        time_str = dt.strftime("%H:%M")
        
        # 1. Universal Stop Check based purely on Time (MTM check is in strategy_runner or notify_exit)
        # Note: 15:00 exit is handled by the runner globally if configured, but we enforce it here.
        if dt.hour >= 15:
            if not self._universal_exit_triggered:
                logger.info(f"[{self.strategy_id}] Universal Time Stop hit at {time_str}")
                self._universal_exit_triggered = True
            return None

        atm_strike = round(close_price / 50) * 50

        # 2. Initial Entry Logic
        if not self._has_traded_today:
            if time_str == "10:39":
                logger.info(f"[{self.strategy_id}] 09:49 AM Initial Entry Triggered at spot={close_price:.2f}")
                self._has_traded_today = True
                return self._build_signal(close_price, atm_strike, "INITIAL_ENTRY")
            return None

        # 3. Re-entry Logic
        # Time constraint: minute must be a multiple of 3
        # Since standard market open is 09:15, trading starts 09:21, subsequent mutiples align cleanly.
        if dt.minute % 3 != 0:
            return None

        # ATM Change constraint
        if self._last_straddle_strike is not None and self._last_combined_premium is not None:
            upper_bound = self._last_straddle_strike + self._last_combined_premium
            lower_bound = self._last_straddle_strike - self._last_combined_premium

            if atm_strike > upper_bound or atm_strike <= lower_bound:
                logger.info(
                    f"[{self.strategy_id}] Re-entry condition met at {time_str}: "
                    f"Current ATM={atm_strike}, bounds=({lower_bound:.2f}, {upper_bound:.2f}]"
                )
                return self._build_signal(close_price, atm_strike, "REENTRY")
            
        return None

    def _build_signal(self, spot_price: float, expected_strike: int, entry_reason: str) -> Dict[str, Any]:
        """Build the SELL_STRADDLE signal dict returned to strategy_runner."""
        return {
            "signal": "SELL_STRADDLE",
            "entry_reason": entry_reason,
            "expected_strike": expected_strike,
            "spot_price": spot_price,
            # For runner to query:
            "option_types": ["CE", "PE"] 
        }

    def notify_exit(self, reason: str, exit_meta: Optional[Dict] = None) -> None:
        """
        Called when a trade is closed.
        reason: 'MOVEMENT_EXIT', 'UNIVERSAL_EXIT', 'EOD', etc.
        """
        logger.info(f"[{self.strategy_id}] notify_exit: {reason}")
        if reason in ("UNIVERSAL_EXIT", "EOD"):
            self._universal_exit_triggered = True
        
        # When an entry is made, the runner calculates the required leg prices and calls this with entry details
        # Alternatively, the runner just manages the trades, and we only need to know WHEN an exit happened.
        pass

    def update_internal_state(self, atm_strike: int, combined_premium: float) -> None:
        """
        Called by strategy_runner right *after* successfully executing a straddle entry,
        to let the strategy know the real executed bounds for its re-entry logic.
        """
        self._last_straddle_strike = atm_strike
        self._last_combined_premium = combined_premium
        logger.debug(f"[{self.strategy_id}] State updated: strike={atm_strike}, premium {combined_premium:.2f}")

    # ── Backtest (Approximation) ──
    def backtest(self, df: pd.DataFrame, quantity: int = 50) -> Dict[str, Any]:
        return super().backtest(df, quantity)
