"""
EMA 9/21 Directional Credit Spread Strategy — 15-Minute Timeframe
==================================================================
Signal Source : EMA(9) / EMA(21) crossover on completed 15-min NIFTY spot candles
Trade Type    : Directional Credit Spreads (Bull Put / Bear Call)
Leg Structure : Sell ≈ ₹125 premium option  +  Buy ≈ ₹25 premium hedge (same expiry)
Exit Rules    : Hard SL (sell-leg+50%), Profit Target (sell-leg−70%), Regime Reversal
Re-Entry      : Only after profitable exit + 2-min cooldown (same regime)
                Blocked completely after SL until next fresh crossover
Expiry Rule   : After 12:00 PM on expiry day → use next weekly expiry
"""
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import pandas as pd
from loguru import logger

from app.strategies.base_strategy import BaseStrategy
from app.utils.indicators import ema


class EMA921CreditSpread(BaseStrategy):
    # ── Identity ──────────────────────────────────────────────────────────────
    strategy_id     = "ema_9_21_credit_spread"
    name            = "EMA 9/21 Credit Spread"
    description     = "EMA 9/21 Credit Spread Strategy"
    timeframe       = "15minute"
    indicators_used = ["EMA 9", "EMA 21"]
    
    # Exposed to frontend via base_strategy metadata
    entry_rules     = ""
    exit_rules      = ""
    sl_logic        = ""
    target_logic    = ""
    fund_required   = 200_000.0  # margin for one NIFTY credit spread
    lot_size        = 75          # current NIFTY lot size

    EMA_FAST  = 9
    EMA_SLOW  = 21
    MIN_CANDLES = EMA_SLOW + 5   # 26 minimum for valid EMA

    # Target premiums to search for on Kite (used by strategy_runner during leg resolution)
    SELL_TARGET_PREMIUM = 125
    BUY_TARGET_PREMIUM  = 25

    def __init__(self):
        super().__init__()
        # ── Internal State Machine ────────────────────────────────────────────
        self._regime: Optional[str] = None          # "BULLISH" | "BEARISH" | None
        self._sl_cooloff: bool = False               # True after SL → block re-entry
        self._pending_reentry_regime: Optional[str] = None  # regime of last profit exit
        self._reentry_allowed_after: Optional[datetime] = None  # 2-min cooldown end
        self._last_crossover_candle: Optional[datetime] = None  # prevent re-fire same candle

        # Auto-start: strategy actively evaluates from server start
        self.start()

    # ── Public API: Strategy Runner calls this every minute (15-min candles) ──

    def run(self, df: pd.DataFrame) -> Optional[Dict[str, Any]]:
        """
        Evaluate on the last completed 15-minute candle.

        df layout (same convention as rest of system):
          df.iloc[-1]  = currently forming candle  ← NEVER evaluate
          df.iloc[-2]  = last fully closed candle   ← "current"  signal row
          df.iloc[-3]  = candle before that          ← "previous" comparison row

        Returns a SELL_SPREAD signal dict on crossover or re-entry, else None.
        """
        if len(df) < self.MIN_CANDLES:
            return None

        df = df.copy()
        df["ema9"]  = ema(df["close"], self.EMA_FAST)
        df["ema21"] = ema(df["close"], self.EMA_SLOW)

        # Drop the live (forming) candle; we only read completed bars
        completed = df.iloc[:-1]
        if len(completed) < 2:
            return None

        cur  = completed.iloc[-1]
        prev = completed.iloc[-2]

        p9, p21 = float(prev["ema9"]), float(prev["ema21"])
        c9, c21 = float(cur["ema9"]),  float(cur["ema21"])

        if any(pd.isna(v) for v in [p9, p21, c9, c21]):
            return None

        # ── Crossover Detection ───────────────────────────────────────────────
        bullish_xover = (p9 <= p21) and (c9 > c21)   # EMA9 crosses above EMA21
        bearish_xover = (p9 >= p21) and (c9 < c21)   # EMA9 crosses below EMA21

        # Get candle datetime to track which candle we are evaluating
        cur_candle_time = cur.get("date", None)

        if bullish_xover:
            if self._last_crossover_candle != cur_candle_time:
                self._last_crossover_candle = cur_candle_time
                logger.info(f"[{self.strategy_id}] BULLISH crossover at {cur_candle_time} "
                            f"EMA9={c9:.2f} EMA21={c21:.2f}")
                self._on_crossover("BULLISH")
                return self._build_signal("BULLISH", "CROSSOVER")
            return None  # already fired on this candle

        if bearish_xover:
            if self._last_crossover_candle != cur_candle_time:
                self._last_crossover_candle = cur_candle_time
                logger.info(f"[{self.strategy_id}] BEARISH crossover at {cur_candle_time} "
                            f"EMA9={c9:.2f} EMA21={c21:.2f}")
                self._on_crossover("BEARISH")
                return self._build_signal("BEARISH", "CROSSOVER")
            return None  # already fired on this candle

        # ── No crossover — check re-entry eligibility ─────────────────────────
        if self._sl_cooloff:
            logger.debug(f"[{self.strategy_id}] SL cooloff active — no re-entry until next crossover")
            return None

        if (
            self._pending_reentry_regime is not None
            and self._pending_reentry_regime == self._regime
            and self._reentry_allowed_after is not None
            and datetime.now() >= self._reentry_allowed_after
        ):
            logger.info(f"[{self.strategy_id}] Re-entry triggered — regime={self._regime}")
            self._pending_reentry_regime = None   # consumed; refreshed on next profitable exit
            return self._build_signal(self._regime, "REENTRY")

        return None

    # ── Lifecycle Callback: Runner calls this after every trade close ─────────

    def notify_exit(self, reason: str) -> None:
        """
        Update internal state based on exit outcome.
          SL_HIT          → activate cooloff, block all re-entries
          STRATEGY_EXIT   → same (reversal exit is treated as SL-equivalent)
          TARGET_HIT      → open re-entry window (2-min cooldown)
          EOD             → treat as SL (no re-entry same day)
        """
        logger.info(f"[{self.strategy_id}] notify_exit: {reason} | regime={self._regime}")

        if reason in ("SL_HIT", "STRATEGY_EXIT", "EOD", "REVERSAL_EXIT"):
            self._sl_cooloff = True
            self._pending_reentry_regime = None
            self._reentry_allowed_after  = None

        elif reason == "TARGET_HIT":
            # Profitable exit → allow re-entry after 2-minute cooldown
            self._sl_cooloff = False
            self._pending_reentry_regime = self._regime
            self._reentry_allowed_after  = datetime.now() + timedelta(minutes=2)

    # ── Private Helpers ───────────────────────────────────────────────────────

    def _on_crossover(self, new_regime: str) -> None:
        """Reset state machine on every fresh crossover."""
        self._regime                 = new_regime
        self._sl_cooloff             = False
        self._pending_reentry_regime = None
        self._reentry_allowed_after  = None

    def _build_signal(self, regime: str, entry_reason: str) -> Dict[str, Any]:
        """Build the SELL_SPREAD signal dict returned to strategy_runner."""
        if regime == "BULLISH":
            spread_type      = "PUT_CREDIT_SPREAD"
            sell_option_type = "PE"
            buy_option_type  = "PE"
        else:
            spread_type      = "CALL_CREDIT_SPREAD"
            sell_option_type = "CE"
            buy_option_type  = "CE"

        return {
            # Sentinel recognized by strategy_runner
            "signal":              "SELL_SPREAD",
            "spread_type":         spread_type,
            "regime":              regime,
            "entry_reason":        entry_reason,
            # Option type for each leg (runner fetches actual symbols + premiums)
            "sell_option_type":    sell_option_type,
            "buy_option_type":     buy_option_type,
            # Target premiums — runner finds closest matching strikes
            "sell_target_premium": self.SELL_TARGET_PREMIUM,
            "buy_target_premium":  self.BUY_TARGET_PREMIUM,
            # These are populated by runner AFTER premium resolution
            "price":  0.0,   # sell leg entry premium (set by runner)
            "sl":     None,  # set by runner: sell_entry * 1.5
            "target": None,  # set by runner: sell_entry * 0.30
        }

    # ── Backtest (spot-price approximation — no live option prices available) ──

    def backtest(self, df: pd.DataFrame, quantity: int = None) -> dict:
        """
        Backtest using spot-close as a proxy for option premium direction.
        Since historical option LTPs are not available, we model:
          - Net credit ≈ SELL_TARGET_PREMIUM - BUY_TARGET_PREMIUM = 100 (fixed)
          - SL is modelled as a spot move > 1.5% against regime
          - Target is modelled as a spot move > 0.8% in regime direction
        This gives a rough win-rate / drawdown view only.
        """
        qty = quantity or self.lot_size

        if df.empty or len(df) < self.MIN_CANDLES:
            return self._empty_backtest()

        df = df.copy().reset_index(drop=True)
        df["ema9"]  = ema(df["close"], self.EMA_FAST)
        df["ema21"] = ema(df["close"], self.EMA_SLOW)

        trades = []
        equity = 0.0
        equity_curve = []
        active = None    # {"regime", "entry_close", "entry_idx"}
        regime = None
        sl_cooloff = False
        NET_CREDIT = self.SELL_TARGET_PREMIUM - self.BUY_TARGET_PREMIUM  # ≈ 100

        for i in range(1, len(df)):
            if pd.isna(df.iloc[i]["ema9"]) or pd.isna(df.iloc[i]["ema21"]):
                continue

            p9  = float(df.iloc[i - 1]["ema9"])
            p21 = float(df.iloc[i - 1]["ema21"])
            c9  = float(df.iloc[i]["ema9"])
            c21 = float(df.iloc[i]["ema21"])
            close = float(df.iloc[i]["close"])

            bull_x = (p9 <= p21) and (c9 > c21)
            bear_x = (p9 >= p21) and (c9 < c21)

            # ── Exit check for active trade ──────────────────────────────────
            if active:
                entry_c = active["entry_close"]
                move_pct = (close - entry_c) / entry_c * 100
                regime_a = active["regime"]

                sl_hit     = (regime_a == "BULLISH" and move_pct < -1.5) or \
                             (regime_a == "BEARISH" and move_pct > +1.5)
                target_hit = (regime_a == "BULLISH" and move_pct > +0.8) or \
                             (regime_a == "BEARISH" and move_pct < -0.8)
                reversal   = (regime_a == "BULLISH" and bear_x) or \
                             (regime_a == "BEARISH" and bull_x)

                exit_reason = None
                pnl = 0.0
                if sl_hit or reversal:
                    exit_reason = "SL_HIT" if sl_hit else "REVERSAL_EXIT"
                    pnl = -NET_CREDIT * qty * 0.5   # approximate SL loss
                    sl_cooloff = True
                elif target_hit:
                    exit_reason = "TARGET_HIT"
                    pnl = NET_CREDIT * qty * 0.7    # approximate profit
                    sl_cooloff = False

                if exit_reason:
                    equity += pnl
                    trades.append({
                        "regime":       regime_a,
                        "entry_close":  entry_c,
                        "exit_close":   close,
                        "entry_idx":    active["entry_idx"],
                        "exit_idx":     i,
                        "pnl":          round(pnl, 2),
                        "exit_reason":  exit_reason,
                    })
                    equity_curve.append({"index": i, "equity": round(equity, 2)})
                    active = None

            # ── New entry / regime change ────────────────────────────────────
            if bull_x or bear_x:
                new_regime = "BULLISH" if bull_x else "BEARISH"
                regime     = new_regime
                sl_cooloff = False

            if not active and regime and not sl_cooloff:
                active = {"regime": regime, "entry_close": close, "entry_idx": i}

        # Force-close EOD
        if active and len(df) > 0:
            last = float(df.iloc[-1]["close"])
            pnl  = 0.0  # neutral approximation for EOD close
            trades.append({
                "regime": active["regime"], "entry_close": active["entry_close"],
                "exit_close": last, "entry_idx": active["entry_idx"],
                "exit_idx": len(df) - 1, "pnl": pnl, "exit_reason": "EOD",
            })
            equity_curve.append({"index": len(df) - 1, "equity": round(equity, 2)})

        if not trades:
            return self._empty_backtest()

        from app.utils.indicators import compute_drawdown
        wins   = [t for t in trades if t["pnl"] > 0]
        losses = [t for t in trades if t["pnl"] < 0]
        eq_s   = pd.Series([e["equity"] for e in equity_curve]) if equity_curve else pd.Series([0])

        return {
            "strategy_id":    self.strategy_id,
            "total_trades":   len(trades),
            "winning_trades": len(wins),
            "losing_trades":  len(losses),
            "win_rate":       round(len(wins) / len(trades) * 100, 2) if trades else 0,
            "total_pnl":      round(equity, 2),
            "max_profit":     round(max(t["pnl"] for t in wins),   2) if wins   else 0,
            "max_loss":       round(min(t["pnl"] for t in losses), 2) if losses else 0,
            "max_drawdown":   round(compute_drawdown(eq_s), 2),
            "equity_curve":   equity_curve,
            "trades":         trades[-20:],
        }
