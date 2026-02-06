#!/usr/bin/env python3
"""Demo: SMA Crossover Strategy

Demonstrates end-to-end backtesting with:
- Hardcoded SMA crossover strategy graph
- AAPL 5-minute data from Polygon
- Full execution and performance analysis
"""

import sys
from datetime import datetime
import pandas as pd
import matplotlib.pyplot as plt

from graph.schema import StrategyGraph, Node, UniverseSpec, TimeConfig, DateRange
from graph.executor import GraphExecutor
from backtest.simulator import run_backtest
from data.polygon_client import PolygonClient
import config


def create_sma_crossover_strategy() -> StrategyGraph:
    """Create a simple SMA crossover strategy graph."""

    nodes = [
        # Market data
        Node(
            id="market_data",
            type="MarketData",
            params={},
            inputs={}
        ),

        # Fast SMA (10 period)
        Node(
            id="sma_fast",
            type="SMA",
            params={"period": 10},
            inputs={"series": ("market_data", "close")}
        ),

        # Slow SMA (50 period)
        Node(
            id="sma_slow",
            type="SMA",
            params={"period": 50},
            inputs={"series": ("market_data", "close")}
        ),

        # Entry condition: fast crosses above slow
        Node(
            id="entry_condition",
            type="Compare",
            params={"op": "cross_up"},
            inputs={
                "a": ("sma_fast", "sma"),
                "b": ("sma_slow", "sma")
            }
        ),

        # Exit condition: fast crosses below slow
        Node(
            id="exit_condition",
            type="Compare",
            params={"op": "cross_down"},
            inputs={
                "a": ("sma_fast", "sma"),
                "b": ("sma_slow", "sma")
            }
        ),

        # Entry signal
        Node(
            id="entry_signal",
            type="EntrySignal",
            params={},
            inputs={"condition": ("entry_condition", "result")}
        ),

        # Exit signal
        Node(
            id="exit_signal",
            type="ExitSignal",
            params={},
            inputs={"condition": ("exit_condition", "result")}
        ),

        # ATR for dynamic stops
        Node(
            id="atr",
            type="ATR",
            params={"period": 14},
            inputs={
                "high": ("market_data", "high"),
                "low": ("market_data", "low"),
                "close": ("market_data", "close")
            }
        ),

        # Stop loss: 1.5x ATR
        Node(
            id="stop_loss",
            type="StopLossATR",
            params={"mult": 1.5},
            inputs={"atr": ("atr", "atr")}
        ),

        # Take profit: 3x ATR
        Node(
            id="take_profit",
            type="TakeProfitATR",
            params={"mult": 3.0},
            inputs={"atr": ("atr", "atr")}
        ),

        # Position sizing: $10,000 per trade
        Node(
            id="position_size",
            type="PositionSizingFixed",
            params={"dollars": 10000.0},
            inputs={}
        ),

        # Bracket order
        Node(
            id="orders",
            type="BracketOrder",
            params={},
            inputs={
                "entry_signal": ("entry_signal", "signal"),
                "exit_signal": ("exit_signal", "signal"),
                "stop_config": ("stop_loss", "stop_config"),
                "tp_config": ("take_profit", "tp_config"),
                "size_config": ("position_size", "size_config")
            }
        ),

        # Risk manager
        Node(
            id="risk_manager",
            type="RiskManagerDaily",
            params={
                "max_loss_pct": 0.02,
                "max_profit_pct": 0.10,
                "max_trades": 10
            },
            inputs={"orders": ("orders", "orders")}
        )
    ]

    return StrategyGraph(
        graph_id="demo_sma_crossover_001",
        name="SMA Crossover (10/50)",
        version="1.0",
        universe=UniverseSpec(type="explicit", symbols=["AAPL"]),
        time=TimeConfig(
            timeframe="5m",
            date_range=DateRange(start="2024-10-01", end="2025-01-01")
        ),
        nodes=nodes,
        outputs={
            "orders": ("risk_manager", "filtered_orders")
        },
        metadata={
            "description": "Simple SMA crossover with ATR-based stops and targets",
            "author": "demo"
        }
    )


def print_metrics(metrics: dict):
    """Print performance metrics in a nice format."""
    print("\n" + "=" * 60)
    print("BACKTEST RESULTS")
    print("=" * 60)

    print(f"\nReturns:")
    print(f"  Total Return:        ${metrics['total_return']:,.2f} ({metrics['total_return_pct']:.2%})")
    print(f"  CAGR:                {metrics['cagr']:.2%}")

    print(f"\nRisk Metrics:")
    print(f"  Sharpe Ratio:        {metrics['sharpe_ratio']:.2f}")
    print(f"  Max Drawdown:        ${metrics['max_drawdown']:,.2f} ({metrics['max_drawdown_pct']:.2%})")

    print(f"\nTrade Statistics:")
    print(f"  Total Trades:        {metrics['trade_count']}")
    print(f"  Win Rate:            {metrics['win_rate']:.2%}")
    print(f"  Average Win:         ${metrics['avg_win']:,.2f}")
    print(f"  Average Loss:        ${metrics['avg_loss']:,.2f}")
    print(f"  Profit Factor:       {metrics['profit_factor']:.2f}")

    if pd.notna(metrics['avg_trade_duration']):
        duration = metrics['avg_trade_duration']
        hours = duration.total_seconds() / 3600
        print(f"  Avg Trade Duration:  {hours:.1f} hours")

    print("=" * 60 + "\n")


def print_trade_summary(trades_df: pd.DataFrame):
    """Print summary of recent trades."""
    if len(trades_df) == 0:
        print("No trades executed.\n")
        return

    print("\nRecent Trades (last 10):")
    print("-" * 60)

    recent = trades_df.tail(10)
    for _, trade in recent.iterrows():
        entry_time = pd.to_datetime(trade['entry_time']).strftime('%Y-%m-%d %H:%M')
        exit_time = pd.to_datetime(trade['exit_time']).strftime('%Y-%m-%d %H:%M')
        pnl_str = f"${trade['pnl']:,.2f}"
        ret_str = f"{trade['return_pct']:.2%}"
        reason = trade['exit_reason']

        print(f"{entry_time} → {exit_time} | {pnl_str:>12} ({ret_str:>8}) | {reason}")

    print("-" * 60 + "\n")


def plot_equity_curve(equity_curve: pd.Series, trades_df: pd.DataFrame):
    """Plot equity curve with trade markers."""
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10), sharex=True)

    # Equity curve
    ax1.plot(equity_curve.index, equity_curve.values, label='Equity', linewidth=2)
    ax1.set_ylabel('Equity ($)', fontsize=12)
    ax1.set_title('Equity Curve', fontsize=14, fontweight='bold')
    ax1.grid(True, alpha=0.3)
    ax1.legend()

    # Mark trades on equity curve
    if len(trades_df) > 0:
        wins = trades_df[trades_df['pnl'] > 0]
        losses = trades_df[trades_df['pnl'] <= 0]

        # Get equity at trade exit times
        for _, trade in wins.iterrows():
            exit_time = pd.to_datetime(trade['exit_time'])
            if exit_time in equity_curve.index:
                ax1.plot(exit_time, equity_curve.loc[exit_time], 'g^', markersize=8, alpha=0.6)

        for _, trade in losses.iterrows():
            exit_time = pd.to_datetime(trade['exit_time'])
            if exit_time in equity_curve.index:
                ax1.plot(exit_time, equity_curve.loc[exit_time], 'rv', markersize=8, alpha=0.6)

    # Drawdown
    running_max = equity_curve.cummax()
    drawdown = (equity_curve - running_max) / running_max * 100

    ax2.fill_between(drawdown.index, drawdown.values, 0, alpha=0.3, color='red')
    ax2.plot(drawdown.index, drawdown.values, color='red', linewidth=1)
    ax2.set_ylabel('Drawdown (%)', fontsize=12)
    ax2.set_xlabel('Date', fontsize=12)
    ax2.set_title('Drawdown', fontsize=14, fontweight='bold')
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig('equity_curve.png', dpi=150, bbox_inches='tight')
    print("📊 Equity curve saved to: equity_curve.png\n")

    # Uncomment to show plot interactively
    # plt.show()


def main():
    """Main demo script."""
    print("\n" + "=" * 60)
    print("SMA CROSSOVER STRATEGY DEMO")
    print("=" * 60 + "\n")

    # Check API key
    if not config.POLYGON_API_KEY:
        print("❌ ERROR: POLYGON_API_KEY not set in .env file")
        print("Please create a .env file with your Polygon API key:")
        print("  POLYGON_API_KEY=your_key_here")
        sys.exit(1)

    # Create strategy
    print("📈 Creating SMA Crossover strategy (10/50 periods)...")
    strategy = create_sma_crossover_strategy()

    # Validate graph structure
    print("✓ Validating strategy graph...")
    try:
        strategy.validate_structure()
        print("✓ Graph structure valid")
    except Exception as e:
        print(f"❌ Graph validation failed: {e}")
        sys.exit(1)

    # Fetch data
    print(f"\n📊 Fetching AAPL 5m data (2024-10-01 to 2025-01-01)...")
    client = PolygonClient()

    try:
        data = client.get_bars(
            symbol="AAPL",
            timeframe="5m",
            start="2024-10-01",
            end="2025-01-01"
        )
        print(f"✓ Fetched {len(data)} bars")

        if len(data) == 0:
            print("❌ No data returned. Check your API key and date range.")
            sys.exit(1)

    except Exception as e:
        print(f"❌ Data fetch failed: {e}")
        sys.exit(1)

    # Execute graph
    print("\n⚙️  Executing strategy graph...")
    executor = GraphExecutor()

    try:
        context = executor.execute(strategy, data)
        print(f"✓ Graph executed successfully ({len(context)} outputs)")
    except Exception as e:
        print(f"❌ Graph execution failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # Get orders config
    orders_config = context[("risk_manager", "filtered_orders")]

    # Run backtest
    print("\n🔬 Running backtest simulation...")
    try:
        results = run_backtest(
            data=data,
            orders_config=orders_config,
            initial_capital=100000.0
        )
        print("✓ Backtest complete")
    except Exception as e:
        print(f"❌ Backtest failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # Print results
    print_metrics(results['metrics'])
    print_trade_summary(results['trades'])

    # Plot equity curve
    if len(results['trades']) > 0:
        print("📊 Generating equity curve plot...")
        plot_equity_curve(results['equity_curve'], results['trades'])
    else:
        print("⚠️  No trades to plot")

    print("✅ Demo complete!\n")


if __name__ == "__main__":
    main()
