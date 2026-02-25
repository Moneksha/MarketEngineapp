"""
Strategy Registry — registers and provides access to all strategies.
Add new strategies here; the rest of the system picks them up automatically.
"""
from app.strategies.ema_9_crossover_option_selling import EMA9CrossoverOptionSelling
from app.strategies.ema_9_21_credit_spread import EMA921CreditSpread
from app.strategies.straddle_2a_vanilla import Straddle2AVanilla
from app.strategies.base_strategy import BaseStrategy
from typing import Dict

# Kite interval map (strategy timeframe → Kite API interval string)
TIMEFRAME_MAP = {
    "1minute":  "minute",
    "3minute":  "3minute",
    "5minute":  "5minute",
    "15minute": "15minute",
    "30minute": "30minute",
    "60minute": "60minute",
    "day":      "day",
}

_registry: Dict[str, BaseStrategy] = {}


def _build_registry() -> Dict[str, BaseStrategy]:
    strategies = [
        EMA9CrossoverOptionSelling(),
        EMA921CreditSpread(),
        Straddle2AVanilla(),
        # VWAPReversalStrategy() — add when ready
        # BreakoutStrategy()     — add when ready
    ]
    return {s.strategy_id: s for s in strategies}


def get_registry() -> Dict[str, BaseStrategy]:
    global _registry
    if not _registry:
        _registry = _build_registry()
    return _registry


def get_strategy(strategy_id: str) -> BaseStrategy:
    reg = get_registry()
    if strategy_id not in reg:
        raise KeyError(f"Strategy '{strategy_id}' not found in registry")
    return reg[strategy_id]


def list_strategies():
    return [s.get_metadata() for s in get_registry().values()]
