"""
EMA 9 Crossover Option Selling Strategy
Timeframe:  1 minute
Indicator:  EMA 9 on NIFTY spot close

ENTRY RULES (STRICT CROSSOVER ONLY — TradingView convention):
  BULLISH crossover: price (close) crosses ABOVE EMA 9
                     i.e. EMA was above close, now below close → SELL ATM PUT (PE)
  BEARISH crossover: price (close) crosses BELOW EMA 9
                     i.e. EMA was below close, now above close → SELL ATM CALL (CE)

  ⚠️  Entry fires ONLY when the relationship flips between the last TWO
      completed candles — NOT when price is merely above/below EMA.

EXIT RULES (STRICT CROSSBACK ONLY):
  EXIT PE  when EMA 9 crosses ABOVE close (bearish crossover, price fell below EMA)
  EXIT CE  when EMA 9 crosses BELOW close (bullish crossover, price rose above EMA)

CONSTRAINTS:
  - No fixed SL / target                  (crossover-based exit only)
  - No multiple simultaneous trades       (runner enforces single trade)
  - Logic evaluated on last CLOSED candle (df.iloc[-2], not df.iloc[-1])
  - Strategy emits intent only            (runner resolves option prices)
  - PnL = (Entry Option Price - Exit Option Price) × lot_size
"""

from typing import Optional, Dict, Any
import pandas as pd
from app.strategies.base_strategy import BaseStrategy
from app.utils.indicators import ema


class EMA9CrossoverOptionSelling(BaseStrategy):
    # ── Identity ──────────────────────────────────────────────────────────────
    strategy_id      = "ema_9_crossover_option_selling"
    name             = "EMA 9 Crossover Option Selling"
    description      = "EMA 9 Crossover Option Selling Strategy"
    timeframe        = "1minute"
    indicators_used  = ["EMA 9", "Volume"]
    entry_rules      = ""
    exit_rules       = ""
    sl_logic         = ""
    target_logic     = ""
    fund_required    = 200_000.0
    lot_size         = 65   # Current NIFTY lot size

    # Require at least EMA_PERIOD + a few candles for a reliable EMA value
    EMA_PERIOD       = 9
    MIN_CANDLES      = EMA_PERIOD + 5   # 14 candles minimum

    def __init__(self):
        super().__init__()
        self.start()  # Auto-start: strategy always active after server restart

    # ── Core logic ────────────────────────────────────────────────────────────

    def run(self, df: pd.DataFrame) -> Optional[Dict[str, Any]]:
        """
        Evaluate strictly on the last two COMPLETED candles.

        df is a DataFrame of historical 1-min OHLCV candles where:
          df.iloc[-1]  = currently forming (open) candle  ← NEVER evaluate this
          df.iloc[-2]  = most recently COMPLETED candle   ← "current" signal row
          df.iloc[-3]  = the candle before that           ← "previous" comparison row

        Returns:
          { "signal": "SELL", "option_type": "PE"|"CE", "sl": None, "target": None }
          on a confirmed crossover, or None if no crossover.
        """
        if len(df) < self.MIN_CANDLES:
            return None

        df = df.copy()
        df["ema9"] = ema(df["close"], self.EMA_PERIOD)

        # Drop the currently-forming candle; only look at completed bars
        completed = df.iloc[:-1]   # everything up to (not including) the live bar

        if len(completed) < 2:
            return None

        # Two most-recent completed candles
        prev = completed.iloc[-2]   # one bar older
        cur  = completed.iloc[-1]   # last fully closed bar

        # ── Stale bar guard: if the latest completed bar is from yesterday,
        #    skip entirely — don't emit signals or locks from historical data.
        import pytz
        today = __import__('datetime').datetime.now(pytz.timezone('Asia/Kolkata')).date()
        try:
            cur_date = cur['date']
            if hasattr(cur_date, 'date'):
                bar_date = cur_date.date()
            else:
                bar_date = __import__('datetime').datetime.fromisoformat(str(cur_date)).date()
            if bar_date < today:
                return None
        except Exception:
            pass

        prev_close = float(prev["close"])
        prev_ema   = float(prev["ema9"])
        cur_close  = float(cur["close"])
        cur_ema    = float(cur["ema9"])

        # Guard: skip if EMA is not yet valid (NaN from first few bars)
        if pd.isna(prev_ema) or pd.isna(cur_ema):
            return None

        # ── Relationship flags ────────────────────────────────────────────────
        # True  → EMA is ABOVE close  (price is below EMA)
        # False → EMA is BELOW close  (price is above EMA)
        prev_ema_above = prev_ema > prev_close
        cur_ema_above  = cur_ema  > cur_close

        # ── Crossover detection (TradingView / standard convention) ───────────
        # BULLISH crossover: PRICE crosses ABOVE EMA
        #   EMA was above price (prev_ema_above=True) → EMA now below price (cur_ema_above=False)
        bullish_crossover = prev_ema_above and (not cur_ema_above)

        # BEARISH crossover: PRICE crosses BELOW EMA
        #   EMA was below price (prev_ema_above=False) → EMA now above price (cur_ema_above=True)
        bearish_crossover = (not prev_ema_above) and cur_ema_above

        if bullish_crossover:
            # Price crossed ABOVE EMA 9 → bullish bias → sell ATM PUT (PE)
            return {
                "signal":      "SELL",
                "option_type": "PE",
                "market_bias": "LONG",
                "price":       cur_close,   # spot; runner overrides with live option LTP
                "sl":          None,
                "target":      None,
            }

        if bearish_crossover:
            # Price crossed BELOW EMA 9 → bearish bias → sell ATM CALL (CE)
            return {
                "signal":      "SELL",
                "option_type": "CE",
                "market_bias": "SHORT",
                "price":       cur_close,   # spot; runner overrides with live option LTP
                "sl":          None,
                "target":      None,
            }

        # No crossover this candle — emit nothing
        return None

    # ── Backtest ──────────────────────────────────────────────────────────────

    def backtest(self, df: pd.DataFrame, quantity: int = 75) -> dict:
        """
        Custom backtest that mirrors live crossover logic exactly.
        Exits are triggered only by an opposite confirmed crossover —
        no fixed SL or target is ever used.

        PnL is computed as if we were selling an option with a proxy price
        equal to the spot close at entry/exit (since historical option prices
        are not available at backtest time).  In live trading, actual option
        LTP is used; this backtest gives a *directional* signal accuracy view.

        Returns the same schema as base_strategy._empty_backtest() /
        base_strategy.backtest() so the API layer stays consistent.
        """
        if df.empty or len(df) < self.MIN_CANDLES:
            return self._empty_backtest()

        df = df.copy().reset_index(drop=True)
        df["ema9"] = ema(df["close"], self.EMA_PERIOD)

        # Pre-compute EMA-above-close flag for each completed candle
        df["ema_above"] = df["ema9"] > df["close"]

        trades = []
        equity = 0.0
        equity_curve = []
        active_trade = None   # { option_type, entry_price, entry_idx }

        # We need at least 2 completed candles before we can detect a crossover,
        # and we treat index i as the "current completed" candle (iloc[-2] in live):
        for i in range(1, len(df)):
            row     = df.iloc[i]
            prev    = df.iloc[i - 1]

            if pd.isna(row["ema9"]) or pd.isna(prev["ema9"]):
                continue

            cur_ema_above  = bool(row["ema_above"])
            prev_ema_above = bool(prev["ema_above"])

            # TradingView convention: bullish = price crosses ABOVE EMA
            bullish_xover = prev_ema_above and (not cur_ema_above)
            bearish_xover = (not prev_ema_above) and cur_ema_above

            close = float(row["close"])

            # ── Check exit for active trade ───────────────────────────────────
            if active_trade:
                should_exit = (
                    (active_trade["option_type"] == "PE" and bearish_xover) or
                    (active_trade["option_type"] == "CE" and bullish_xover)
                )
                if should_exit:
                    exit_price = close
                    # Sell-side PnL: entry premium collected - exit premium paid back
                    pnl = (active_trade["entry_price"] - exit_price) * quantity
                    equity += pnl
                    trades.append({
                        "direction":    "SELL",
                        "option_type":  active_trade["option_type"],
                        "entry_price":  active_trade["entry_price"],
                        "exit_price":   exit_price,
                        "pnl":          round(pnl, 2),
                        "exit_reason":  "CROSSOVER_EXIT",
                        "entry_candle": active_trade["entry_idx"],
                        "exit_candle":  i,
                    })
                    equity_curve.append({"index": i, "equity": round(equity, 2)})
                    active_trade = None
                    # Fall through — check for new entry on same crossover

            # ── Check entry if no active trade ────────────────────────────────
            if active_trade is None:
                if bullish_xover:
                    active_trade = {"option_type": "PE", "entry_price": close, "entry_idx": i}
                elif bearish_xover:
                    active_trade = {"option_type": "CE", "entry_price": close, "entry_idx": i}

        # Force-close any open position at EOD
        if active_trade and len(df) > 0:
            exit_price = float(df.iloc[-1]["close"])
            pnl = (active_trade["entry_price"] - exit_price) * quantity
            equity += pnl
            trades.append({
                "direction":    "SELL",
                "option_type":  active_trade["option_type"],
                "entry_price":  active_trade["entry_price"],
                "exit_price":   exit_price,
                "pnl":          round(pnl, 2),
                "exit_reason":  "EOD",
                "entry_candle": active_trade["entry_idx"],
                "exit_candle":  len(df) - 1,
            })
            equity_curve.append({"index": len(df) - 1, "equity": round(equity, 2)})

        if not trades:
            return self._empty_backtest()

        from app.utils.indicators import compute_drawdown
        wins   = [t for t in trades if t["pnl"] > 0]
        losses = [t for t in trades if t["pnl"] <= 0]
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
