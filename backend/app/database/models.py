from datetime import datetime
from typing import Optional
from sqlalchemy import (
    Column, Integer, String, Numeric, Boolean, DateTime,
    ForeignKey, Text, JSON, Date, UniqueConstraint
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database.base import Base


class Instrument(Base):
    __tablename__ = "instruments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(200))
    exchange = Column(String(20), default="NSE")
    token = Column(Integer)           # Kite instrument token
    lot_size = Column(Integer, default=1)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Strategy(Base):
    __tablename__ = "strategies"

    id = Column(String(50), primary_key=True)
    name = Column(String(200), nullable=False)
    timeframe = Column(String(10))
    description = Column(Text)
    is_active = Column(Boolean, default=True)
    version = Column(Integer, default=1)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    trades = relationship("Trade", back_populates="strategy")
    pnl_snapshots = relationship("PnLSnapshot", back_populates="strategy")
    backtest_results = relationship("BacktestResult", back_populates="strategy")
    strategy_runs = relationship("StrategyRun", back_populates="strategy")


class StrategyRun(Base):
    __tablename__ = "strategy_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    strategy_id = Column(String(50), ForeignKey("strategies.id"), nullable=False)
    run_at = Column(DateTime(timezone=True), server_default=func.now())
    signal = Column(String(20))       # BUY / SELL / NONE
    price = Column(Numeric(12, 2))
    candle_data = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    strategy = relationship("Strategy", back_populates="strategy_runs")


class Trade(Base):
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, autoincrement=True)
    strategy_id = Column(String(50), ForeignKey("strategies.id"), nullable=False)
    symbol = Column(String(50), nullable=False)
    direction = Column(String(10), nullable=False)    # BUY / SELL
    entry_price = Column(Numeric(12, 2), nullable=False)
    entry_time = Column(DateTime(timezone=True), nullable=False)
    exit_price = Column(Numeric(12, 2))
    exit_time = Column(DateTime(timezone=True))
    quantity = Column(Integer, nullable=False, default=50)
    sl_price = Column(Numeric(12, 2))
    target_price = Column(Numeric(12, 2))
    pnl = Column(Numeric(12, 2))
    status = Column(String(20), nullable=False, default="ACTIVE")
    signal_source = Column(String(50))
    signal_data = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    strategy = relationship("Strategy", back_populates="trades")


class PnLSnapshot(Base):
    __tablename__ = "pnl_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    strategy_id = Column(String(50), ForeignKey("strategies.id"), nullable=False)
    snapshot_at = Column(DateTime(timezone=True), server_default=func.now())
    realized_pnl = Column(Numeric(12, 2), default=0)
    unrealized_pnl = Column(Numeric(12, 2), default=0)
    total_equity = Column(Numeric(12, 2), default=0)
    trade_count = Column(Integer, default=0)

    strategy = relationship("Strategy", back_populates="pnl_snapshots")


class BacktestResult(Base):
    __tablename__ = "backtest_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    strategy_id = Column(String(50), ForeignKey("strategies.id"), nullable=False)
    run_date = Column(Date, nullable=False)
    from_date = Column(Date)
    to_date = Column(Date)
    total_trades = Column(Integer, default=0)
    winning_trades = Column(Integer, default=0)
    losing_trades = Column(Integer, default=0)
    win_rate = Column(Numeric(5, 2))
    total_pnl = Column(Numeric(12, 2))
    max_profit = Column(Numeric(12, 2))
    max_loss = Column(Numeric(12, 2))
    max_drawdown = Column(Numeric(12, 2))
    equity_curve = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    strategy = relationship("Strategy", back_populates="backtest_results")


class NiftyCandle(Base):
    """
    Persistent OHLCV candle store for NIFTY.
    One row per (symbol, interval, timestamp) — unique constraint ensures idempotent upserts.
    Primary use: historical indicator calculation (EMA, ATR, etc.) without re-fetching from Kite.
    """
    __tablename__ = "nifty_candles"

    id        = Column(Integer, primary_key=True, autoincrement=True)
    symbol    = Column(String(20), nullable=False, default="NIFTY 50", index=True)
    interval  = Column(String(10), nullable=False, default="1minute", index=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    open      = Column(Numeric(12, 2), nullable=False)
    high      = Column(Numeric(12, 2), nullable=False)
    low       = Column(Numeric(12, 2), nullable=False)
    close     = Column(Numeric(12, 2), nullable=False)
    volume    = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("symbol", "interval", "timestamp", name="uq_nifty_candle"),
    )


class EquityPrice(Base):
    """
    Unified equity OHLCV store for the backtest engine.
    One row per (symbol, datetime) at 1-minute resolution.
    Higher timeframes are resampled in-memory by the engine.
    """
    __tablename__ = "equity_prices"

    id       = Column(Integer, primary_key=True, autoincrement=True)
    symbol   = Column(String(50), nullable=False, index=True)
    datetime = Column(DateTime, nullable=False, index=True)
    open     = Column(Numeric(12, 2))
    high     = Column(Numeric(12, 2))
    low      = Column(Numeric(12, 2))
    close    = Column(Numeric(12, 2))
    volume   = Column(Integer, default=0)

    __table_args__ = (
        UniqueConstraint("symbol", "datetime", name="uq_equity_price"),
    )

