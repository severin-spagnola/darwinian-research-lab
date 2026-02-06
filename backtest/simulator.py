"""Vectorized backtesting simulator with strict execution rules.

Execution model:
- Entry signal at bar t close → fill at bar t+1 open
- Stop/target checked using bar t high/low
- Exit signal at bar t close → fill at bar t+1 open
- Risk manager enforces daily P&L limits and trade count limits
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Trade:
    """Represents a single completed trade."""
    entry_time: datetime
    entry_price: float
    exit_time: datetime
    exit_price: float
    pnl: float
    return_pct: float
    shares: int
    hit_stop: bool
    hit_target: bool
    exit_reason: str  # "stop", "target", "signal", "eod"


class BacktestSimulator:
    """Vectorized backtester with realistic execution model."""

    def __init__(self, initial_capital: float = 100000.0):
        self.initial_capital = initial_capital

    @staticmethod
    def _get_bar_timestamp(bar: pd.Series, data: pd.DataFrame, idx: int) -> pd.Timestamp:
        """Extract timestamp from bar (handles both column and index formats).

        Args:
            bar: Row from OHLCV DataFrame
            data: Original DataFrame
            idx: Row index position

        Returns:
            Timestamp for this bar
        """
        if 'timestamp' in bar.index:
            return bar['timestamp']
        else:
            # Timestamp is in the DataFrame index
            return data.index[idx]

    def run(
        self,
        data: pd.DataFrame,
        entry_signals: pd.Series,
        exit_signals: Optional[pd.Series],
        stop_config: Dict[str, Any],
        tp_config: Dict[str, Any],
        size_config: Dict[str, Any],
        risk_limits: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Run backtest simulation.

        Args:
            data: OHLCV DataFrame with columns: timestamp, open, high, low, close, volume
            entry_signals: Boolean series indicating entry signals (at close)
            exit_signals: Boolean series indicating exit signals (at close), optional
            stop_config: Stop loss configuration dict
            tp_config: Take profit configuration dict
            size_config: Position sizing configuration dict
            risk_limits: Risk manager limits (max_loss_pct, max_profit_pct, max_trades)

        Returns:
            Dict with keys: trades (DataFrame), equity_curve (Series), metrics (Dict)
        """
        # Reset index to integer for easier iteration
        data = data.reset_index(drop=True)
        entry_signals = entry_signals.reset_index(drop=True)
        if exit_signals is not None:
            exit_signals = exit_signals.reset_index(drop=True)
        else:
            exit_signals = pd.Series([False] * len(data), index=data.index)

        # Track state
        trades = []
        position = None  # Current open position
        equity = self.initial_capital
        daily_pnl = 0.0
        daily_trades = 0
        current_date = None

        # Iterate through bars
        for i in range(len(data) - 1):  # -1 because we need next bar for fills
            bar = data.iloc[i]
            next_bar = data.iloc[i + 1]

            # Check if new day (reset daily counters)
            bar_date = pd.to_datetime(self._get_bar_timestamp(bar, data, i)).date()
            if current_date is None or bar_date != current_date:
                current_date = bar_date
                daily_pnl = 0.0
                daily_trades = 0

            # If we have a position, check stops/targets/exits
            if position is not None:
                exit_price = None
                exit_reason = None
                hit_stop = False
                hit_target = False

                # Calculate stop and target prices for this bar
                stop_price = self._calculate_stop_price(
                    position['entry_price'], stop_config, position.get('atr_value')
                )
                target_price = self._calculate_target_price(
                    position['entry_price'], tp_config, position.get('atr_value')
                )

                # Check if stop or target hit during this bar
                # Assume worst case: if both hit, stop hits first
                if next_bar['low'] <= stop_price:
                    exit_price = stop_price
                    exit_reason = "stop"
                    hit_stop = True
                elif next_bar['high'] >= target_price:
                    exit_price = target_price
                    exit_reason = "target"
                    hit_target = True
                elif exit_signals.iloc[i]:
                    # Exit signal at close of bar i, fill at open of bar i+1
                    exit_price = next_bar['open']
                    exit_reason = "signal"

                # Close position if exit triggered
                if exit_price is not None:
                    pnl = (exit_price - position['entry_price']) * position['shares']
                    return_pct = (exit_price - position['entry_price']) / position['entry_price']

                    trade = Trade(
                        entry_time=position['entry_time'],
                        entry_price=position['entry_price'],
                        exit_time=self._get_bar_timestamp(next_bar, data, i + 1),
                        exit_price=exit_price,
                        pnl=pnl,
                        return_pct=return_pct,
                        shares=position['shares'],
                        hit_stop=hit_stop,
                        hit_target=hit_target,
                        exit_reason=exit_reason,
                    )
                    trades.append(trade)

                    equity += pnl
                    daily_pnl += pnl
                    position = None

            # Check for entry signals (only if no position)
            if position is None and entry_signals.iloc[i]:
                # Check risk limits if configured
                if risk_limits:
                    # Check daily loss limit
                    max_loss_pct = risk_limits.get('max_loss_pct')
                    if max_loss_pct is not None:
                        max_loss = self.initial_capital * max_loss_pct
                        if daily_pnl < -max_loss:
                            continue  # Skip entry, hit daily loss limit

                    # Check daily profit limit
                    max_profit_pct = risk_limits.get('max_profit_pct')
                    if max_profit_pct is not None:
                        max_profit = self.initial_capital * max_profit_pct
                        if daily_pnl > max_profit:
                            continue  # Skip entry, hit daily profit target

                    # Check max trades limit
                    max_trades = risk_limits.get('max_trades')
                    if max_trades is not None and daily_trades >= max_trades:
                        continue  # Skip entry, hit daily trade limit

                # Get ATR value if needed for stop/target
                atr_value = None
                atr_required = stop_config.get('type') == 'atr' or tp_config.get('type') == 'atr'

                if atr_required:
                    atr_series = stop_config.get('atr')
                    if atr_series is None:
                        atr_series = tp_config.get('atr')
                    if atr_series is not None and i < len(atr_series):
                        atr_value = atr_series.iloc[i]

                    # Skip entry if ATR is required but not available (warmup period or NaN)
                    if atr_value is None or np.isnan(atr_value):
                        continue  # Skip this entry - indicator_warmup_unsatisfied

                # Calculate position size
                shares = self._calculate_position_size(
                    next_bar['open'], equity, size_config
                )

                if shares > 0:
                    # Entry signal at close of bar i, fill at open of bar i+1
                    position = {
                        'entry_time': self._get_bar_timestamp(next_bar, data, i + 1),
                        'entry_price': next_bar['open'],
                        'shares': shares,
                        'atr_value': atr_value,
                    }
                    daily_trades += 1

        # Close any remaining position at last bar
        if position is not None:
            last_bar = data.iloc[-1]
            pnl = (last_bar['close'] - position['entry_price']) * position['shares']
            return_pct = (last_bar['close'] - position['entry_price']) / position['entry_price']

            trade = Trade(
                entry_time=position['entry_time'],
                entry_price=position['entry_price'],
                exit_time=self._get_bar_timestamp(last_bar, data, len(data) - 1),
                exit_price=last_bar['close'],
                pnl=pnl,
                return_pct=return_pct,
                shares=position['shares'],
                hit_stop=False,
                hit_target=False,
                exit_reason="eod",
            )
            trades.append(trade)
            equity += pnl

        # Convert trades to DataFrame
        if trades:
            trades_df = pd.DataFrame([
                {
                    'entry_time': t.entry_time,
                    'entry_price': t.entry_price,
                    'exit_time': t.exit_time,
                    'exit_price': t.exit_price,
                    'pnl': t.pnl,
                    'return_pct': t.return_pct,
                    'shares': t.shares,
                    'hit_stop': t.hit_stop,
                    'hit_target': t.hit_target,
                    'exit_reason': t.exit_reason,
                }
                for t in trades
            ])
        else:
            trades_df = pd.DataFrame(columns=[
                'entry_time', 'entry_price', 'exit_time', 'exit_price',
                'pnl', 'return_pct', 'shares', 'hit_stop', 'hit_target', 'exit_reason'
            ])

        # Calculate equity curve
        equity_curve = self._calculate_equity_curve(trades, data)

        # Calculate metrics
        metrics = self._calculate_metrics(trades_df, equity_curve, data)

        return {
            'trades': trades_df,
            'equity_curve': equity_curve,
            'metrics': metrics,
        }

    def _calculate_stop_price(
        self, entry_price: float, stop_config: Dict[str, Any], atr_value: Optional[float]
    ) -> float:
        """Calculate stop loss price.

        Note: ATR-based stops require atr_value to be valid.
        Entry should be skipped if ATR is NaN (handled in run() method).
        """
        if stop_config['type'] == 'fixed':
            return entry_price - stop_config['points']
        elif stop_config['type'] == 'atr':
            # ATR value should always be valid here (checked before entry)
            if atr_value is None or np.isnan(atr_value):
                raise ValueError("ATR-based stop requires valid ATR value")
            return entry_price - (atr_value * stop_config['mult'])
        else:
            raise ValueError(f"Unknown stop config type: {stop_config['type']}")

    def _calculate_target_price(
        self, entry_price: float, tp_config: Dict[str, Any], atr_value: Optional[float]
    ) -> float:
        """Calculate take profit price.

        Note: ATR-based targets require atr_value to be valid.
        Entry should be skipped if ATR is NaN (handled in run() method).
        """
        if tp_config['type'] == 'fixed':
            return entry_price + tp_config['points']
        elif tp_config['type'] == 'atr':
            # ATR value should always be valid here (checked before entry)
            if atr_value is None or np.isnan(atr_value):
                raise ValueError("ATR-based target requires valid ATR value")
            return entry_price + (atr_value * tp_config['mult'])
        else:
            raise ValueError(f"Unknown take profit config type: {tp_config['type']}")

    def _calculate_position_size(
        self, entry_price: float, equity: float, size_config: Dict[str, Any]
    ) -> int:
        """Calculate position size in shares."""
        if size_config['type'] == 'fixed':
            dollars = size_config['dollars']
            shares = int(dollars / entry_price)
        elif size_config['type'] == 'pct':
            pct = size_config['pct']
            dollars = equity * pct
            shares = int(dollars / entry_price)
        else:
            raise ValueError(f"Unknown size config type: {size_config['type']}")

        return max(shares, 0)

    def _calculate_equity_curve(
        self, trades: list, data: pd.DataFrame
    ) -> pd.Series:
        """Calculate equity curve over time."""
        # Get timestamp series or index (handle both column and index formats)
        if 'timestamp' in data.columns:
            timestamps = data['timestamp']
            use_index = False
        elif isinstance(data.index, pd.DatetimeIndex):
            timestamps = data.index
            use_index = True
        else:
            # Fallback for non-datetime index
            timestamps = pd.RangeIndex(len(data))
            use_index = True

        if not trades:
            return pd.Series([self.initial_capital] * len(data), index=timestamps)

        # Create series of cumulative PnL
        if use_index:
            equity_points = [(timestamps[0], self.initial_capital)]
        else:
            equity_points = [(timestamps.iloc[0], self.initial_capital)]

        for trade in trades:
            # Add equity after this trade
            current_equity = equity_points[-1][1] + trade.pnl
            equity_points.append((trade.exit_time, current_equity))

        # Convert to Series and reindex to match data timestamps
        equity_df = pd.DataFrame(equity_points, columns=['timestamp', 'equity'])
        equity_series = equity_df.set_index('timestamp')['equity']

        # Forward fill to match all data timestamps
        full_equity = equity_series.reindex(timestamps, method='ffill')
        full_equity = full_equity.fillna(self.initial_capital)

        return full_equity

    def _calculate_metrics(
        self, trades_df: pd.DataFrame, equity_curve: pd.Series, data: pd.DataFrame
    ) -> Dict[str, Any]:
        """Calculate performance metrics."""
        if len(trades_df) == 0:
            return {
                'total_return': 0.0,
                'total_return_pct': 0.0,
                'cagr': 0.0,
                'sharpe_ratio': 0.0,
                'max_drawdown': 0.0,
                'max_drawdown_pct': 0.0,
                'trade_count': 0,
                'win_rate': 0.0,
                'avg_win': 0.0,
                'avg_loss': 0.0,
                'profit_factor': 0.0,
                'avg_trade_duration': pd.Timedelta(0),
            }

        # Get timestamps (handle both column and index formats)
        if 'timestamp' in data.columns:
            timestamps = data['timestamp']
        elif isinstance(data.index, pd.DatetimeIndex):
            # Index is datetime, access directly
            start_ts = data.index[0]
            end_ts = data.index[-1]
            delta_ts = data.index[1] - data.index[0] if len(data) > 1 else pd.Timedelta(minutes=5)
        else:
            # Index is not datetime, can't calculate time-based metrics
            start_ts = end_ts = delta_ts = None

        # Total return
        final_equity = equity_curve.iloc[-1]
        total_return = final_equity - self.initial_capital
        total_return_pct = total_return / self.initial_capital

        # CAGR
        if start_ts is not None and end_ts is not None:
            years = (end_ts - start_ts).days / 365.25
            cagr = ((final_equity / self.initial_capital) ** (1 / years) - 1) if years > 0 else 0.0
        else:
            cagr = 0.0

        # Sharpe ratio (annualized)
        returns = equity_curve.pct_change().dropna()
        if len(returns) > 0 and returns.std() > 0 and delta_ts is not None:
            # Estimate bars per day (rough approximation)
            timeframe_mins = delta_ts.total_seconds() / 60
            bars_per_day = 390 / timeframe_mins if timeframe_mins > 0 else 78  # 390 min market day
            sharpe_ratio = (returns.mean() / returns.std()) * np.sqrt(252 * bars_per_day)
        else:
            sharpe_ratio = 0.0

        # Max drawdown
        running_max = equity_curve.cummax()
        drawdown = equity_curve - running_max
        max_drawdown = drawdown.min()
        max_drawdown_pct = (drawdown / running_max).min()

        # Trade statistics
        wins = trades_df[trades_df['pnl'] > 0]
        losses = trades_df[trades_df['pnl'] < 0]

        trade_count = len(trades_df)
        win_rate = len(wins) / trade_count if trade_count > 0 else 0.0
        avg_win = wins['pnl'].mean() if len(wins) > 0 else 0.0
        avg_loss = losses['pnl'].mean() if len(losses) > 0 else 0.0

        total_wins = wins['pnl'].sum() if len(wins) > 0 else 0.0
        total_losses = abs(losses['pnl'].sum()) if len(losses) > 0 else 0.0
        profit_factor = total_wins / total_losses if total_losses > 0 else 0.0

        # Average trade duration
        trades_df['duration'] = pd.to_datetime(trades_df['exit_time']) - pd.to_datetime(trades_df['entry_time'])
        avg_trade_duration = trades_df['duration'].mean()

        return {
            'total_return': total_return,
            'total_return_pct': total_return_pct,
            'cagr': cagr,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': max_drawdown,
            'max_drawdown_pct': max_drawdown_pct,
            'trade_count': trade_count,
            'win_rate': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor,
            'avg_trade_duration': avg_trade_duration,
        }


def run_backtest(
    data: pd.DataFrame,
    orders_config: Dict[str, Any],
    initial_capital: float = 100000.0,
) -> Dict[str, Any]:
    """Convenience function to run backtest from orders config.

    Args:
        data: OHLCV DataFrame
        orders_config: Orders dict from BracketOrder node output
        initial_capital: Starting capital

    Returns:
        Dict with trades, equity_curve, metrics
    """
    simulator = BacktestSimulator(initial_capital=initial_capital)

    # Extract components from orders config
    entry_signals = orders_config['entry_signal']
    exit_signals = orders_config.get('exit_signal')
    stop_config = orders_config['stop_config']
    tp_config = orders_config['tp_config']
    size_config = orders_config['size_config']
    risk_limits = orders_config.get('risk_limits')

    return simulator.run(
        data=data,
        entry_signals=entry_signals,
        exit_signals=exit_signals,
        stop_config=stop_config,
        tp_config=tp_config,
        size_config=size_config,
        risk_limits=risk_limits,
    )
