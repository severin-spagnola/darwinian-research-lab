"""Backtesting engine for strategy execution."""

from .simulator import BacktestSimulator, run_backtest

__all__ = ['BacktestSimulator', 'run_backtest']
