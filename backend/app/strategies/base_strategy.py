"""
BaseStrategy — Abstract base class for all trading strategies.
Every strategy must implement: run(), get_metadata(), and backtest().
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import pandas as pd
from app.utils.indicators import candles_to_dataframe, compute_drawdown


class BaseStrategy(ABC):
    """Abstract base class. All strategies inherit from this."""

    strategy_id: str = ""
    name: str = ""
    description: str = ""
    timeframe: str = "5minute"
    indicators_used: List[str] = []
    entry_rules: str = ""
    exit_rules: str = ""
    sl_logic: str = ""
    target_logic: str = ""
    fund_required: float = 100000.0
    lot_size: int = 50
    is_positional: bool = False  # Flag for multi-day carry-forward

    def __init__(self):
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self):
        self._running = True

    def stop(self):
        self._running = False

    def notify_exit(self, reason: str) -> None:
        """
        Called by the strategy runner after any trade exits.
        Override in stateful strategies to update internal state machine.
        reason: 'SL_HIT' | 'TARGET_HIT' | 'EOD' | 'STRATEGY_EXIT' | 'REVERSAL_EXIT'
        """
        pass

    @abstractmethod
    def run(self, df: pd.DataFrame) -> Optional[Dict[str, Any]]:
        """
        Given a DataFrame of OHLCV candles, return a signal dict or None.
        Signal dict: { "signal": "BUY"|"SELL", "price": float, "sl": float, "target": float }
        """
        pass

    def backtest(self, df: pd.DataFrame, quantity: int = 50) -> Dict[str, Any]:
        """
        Run strategy on historical candles and return performance metrics.
        Default implementation — strategies can override for custom logic.
        """
        if df.empty or len(df) < 30:
            return self._empty_backtest()

        trades = []
        equity = 0.0
        equity_curve = []
        active_trade = None

        for i in range(30, len(df)):
            window = df.iloc[:i + 1].copy()
            candle = df.iloc[i]

            # Check SL/Target for active trade
            if active_trade:
                current_price = float(candle["close"])
                direction = active_trade["direction"]
                exit_reason = None

                if direction == "BUY":
                    if current_price <= active_trade["sl"]:
                        exit_reason = "SL_HIT"
                    elif current_price >= active_trade["target"]:
                        exit_reason = "TARGET_HIT"
                elif direction == "SELL":
                    if current_price >= active_trade["sl"]:
                        exit_reason = "SL_HIT"
                    elif current_price <= active_trade["target"]:
                        exit_reason = "TARGET_HIT"

                if exit_reason:
                    pnl = (current_price - active_trade["entry_price"]) * quantity
                    if direction == "SELL":
                        pnl = -pnl
                    equity += pnl
                    trades.append({
                        "direction": direction,
                        "entry_price": active_trade["entry_price"],
                        "exit_price": current_price,
                        "pnl": round(pnl, 2),
                        "exit_reason": exit_reason,
                        "entry_candle": active_trade["candle_index"],
                        "exit_candle": i,
                    })
                    equity_curve.append({"index": i, "equity": round(equity, 2)})
                    active_trade = None
                    continue

            # Look for new signal
            if not active_trade:
                try:
                    signal = self.run(window)
                except Exception:
                    signal = None

                if signal and signal.get("signal") in ("BUY", "SELL"):
                    active_trade = {
                        "direction": signal["signal"],
                        "entry_price": signal["price"],
                        "sl": signal["sl"],
                        "target": signal["target"],
                        "candle_index": i,
                    }

        # Force-close any open trade at end
        if active_trade and len(df) > 0:
            last_price = float(df.iloc[-1]["close"])
            pnl = (last_price - active_trade["entry_price"]) * quantity
            if active_trade["direction"] == "SELL":
                pnl = -pnl
            equity += pnl
            trades.append({
                "direction": active_trade["direction"],
                "entry_price": active_trade["entry_price"],
                "exit_price": last_price,
                "pnl": round(pnl, 2),
                "exit_reason": "EOD",
            })
            equity_curve.append({"index": len(df) - 1, "equity": round(equity, 2)})

        # Stats
        if not trades:
            return self._empty_backtest()

        wins = [t for t in trades if t["pnl"] > 0]
        losses = [t for t in trades if t["pnl"] <= 0]
        eq_series = pd.Series([e["equity"] for e in equity_curve]) if equity_curve else pd.Series([0])
        max_drawdown = compute_drawdown(eq_series)

        return {
            "strategy_id": self.strategy_id,
            "total_trades": len(trades),
            "winning_trades": len(wins),
            "losing_trades": len(losses),
            "win_rate": round(len(wins) / len(trades) * 100, 2) if trades else 0,
            "total_pnl": round(equity, 2),
            "max_profit": round(max(t["pnl"] for t in wins), 2) if wins else 0,
            "max_loss": round(min(t["pnl"] for t in losses), 2) if losses else 0,
            "max_drawdown": round(max_drawdown, 2),
            "equity_curve": equity_curve,
            "trades": trades[-20:],  # last 20 for display
        }

    def _empty_backtest(self) -> Dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "total_trades": 0, "winning_trades": 0, "losing_trades": 0,
            "win_rate": 0, "total_pnl": 0, "max_profit": 0,
            "max_loss": 0, "max_drawdown": 0,
            "equity_curve": [], "trades": [],
        }

    def get_metadata(self) -> Dict[str, Any]:
        return {
            "id": self.strategy_id,
            "name": self.name,
            "description": self.description,
            "timeframe": self.timeframe,
            "indicators": self.indicators_used,
            "entry_rules": self.entry_rules,
            "exit_rules": self.exit_rules,
            "sl_logic": self.sl_logic,
            "target_logic": self.target_logic,
            "fund_required": self.fund_required,
            "lot_size": self.lot_size,
            "is_running": self._running,
            "is_positional": self.is_positional,
        }
