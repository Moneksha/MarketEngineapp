"""
registry.py
-----------
Registry for backtest strategies.
"""
from typing import Dict, Type
from .base import BaseBacktestStrategy
from .ema_trend import EMATrendStrategy
from .ema_crossover import EMACrossoverStrategy
from .supertrend import SupertrendStrategy
from .rsi_strategy import RSIStrategy
from .macd_strategy import MACDStrategy
from .bollinger_band_strategy import BollingerBandStrategy

STRATEGIES: Dict[str, Type[BaseBacktestStrategy]] = {
    "ema_trend": EMATrendStrategy,
    "ema_crossover": EMACrossoverStrategy,
    "supertrend": SupertrendStrategy,
    "rsi": RSIStrategy,
    "macd": MACDStrategy,
    "bollinger": BollingerBandStrategy,
}

def get_strategy(strategy_id: str) -> BaseBacktestStrategy:
    strat_class = STRATEGIES.get(strategy_id)
    if not strat_class:
        raise ValueError(f"Unknown strategy ID: {strategy_id}")
    return strat_class()
