#!/usr/bin/env python3
"""
Test Darwin survivor floor and rescue-from-best-dead mechanisms with synthetic data.
No mutations - just verify selection logic works.
"""

import sys
import pandas as pd
import numpy as np
from graph.schema import StrategyGraph, Node, UniverseSpec, TimeConfig, DateRange
from validation.evaluation import Phase3Config
from evolution.darwin import run_darwin


def make_test_data(n_bars=1000):
    """Create synthetic test data."""
    dates = pd.date_range("2024-01-01", periods=n_bars, freq="5min")
    np.random.seed(42)
    close = 100.0 + np.cumsum(np.random.randn(n_bars) * 0.3)
    df = pd.DataFrame({
        "open": close * 0.999,
        "high": close * 1.002,
        "low": close * 0.998,
        "close": close,
        "volume": 1000,
    }, index=dates)
    df.index.name = 'timestamp'
    return df


def make_simple_trading_strategy():
    """Create a strategy that trades frequently."""
    return StrategyGraph(
        graph_id="simple_trader",
        name="Simple Frequent Trader",
        version="1.0",
        nodes=[
            Node(id="market", type="MarketData", params={}, inputs={}),
            Node(id="entry_condition", type="Compare", params={"op": ">"},
                 inputs={"a": ("market", "close"), "b": ("market", "open")}),
            Node(id="entry_signal", type="EntrySignal", params={},
                 inputs={"condition": ("entry_condition", "result")}),
            Node(id="exit_condition", type="Compare", params={"op": "<"},
                 inputs={"a": ("market", "close"), "b": ("market", "open")}),
            Node(id="exit_signal", type="ExitSignal", params={},
                 inputs={"condition": ("exit_condition", "result")}),
            Node(id="stop_fixed", type="StopLossFixed", params={"points": 2.0}, inputs={}),
            Node(id="tp_fixed", type="TakeProfitFixed", params={"points": 5.0}, inputs={}),
            Node(id="position_size", type="PositionSizingFixed", params={"dollars": 5000.0}, inputs={}),
            Node(id="bracket", type="BracketOrder", params={},
                 inputs={
                     "entry_signal": ("entry_signal", "signal"),
                     "exit_signal": ("exit_signal", "signal"),
                     "stop_config": ("stop_fixed", "stop_config"),
                     "tp_config": ("tp_fixed", "tp_config"),
                     "size_config": ("position_size", "size_config"),
                 }),
            Node(id="risk_manager", type="RiskManagerDaily",
                 params={"max_loss_pct": 0.50, "max_profit_pct": 1.0, "max_trades": 50},
                 inputs={"orders": ("bracket", "orders")}),
        ],
        outputs={"orders": ("risk_manager", "filtered_orders")},
        metadata={"test": True},
        universe=UniverseSpec(type="explicit", symbols=["TEST"]),
        time=TimeConfig(
            timeframe="5m",
            date_range=DateRange(start="2024-01-01", end="2024-12-31"),
        ),
    )


print("="*80)
print("TESTING DARWIN SURVIVOR FLOOR AND RESCUE-FROM-BEST-DEAD")
print("="*80)
print()

# Generate synthetic data
print("[DATA GENERATION]")
data = make_test_data(n_bars=1000)
print(f"Generated {len(data)} bars of synthetic data")
print()

# Create strategy
strategy = make_simple_trading_strategy()

# Test 1: Survivor Floor
print("="*80)
print("TEST 1: SURVIVOR FLOOR")
print("="*80)
print()

phase3_config = Phase3Config(
    enabled=True,
    mode="episodes",
    n_episodes=3,
    min_months=1,
    max_months=2,
    min_bars=50,
    seed=42,
    sampling_mode="random",
    min_trades_per_episode=100,  # Very high - will kill all
    regime_penalty_weight=0.3,
    abort_on_all_episode_failures=False,
)

universe = UniverseSpec(type="explicit", symbols=["TEST"])
time_config = TimeConfig(
    timeframe="5m",
    date_range=DateRange(start="2024-01-01", end="2024-12-31"),
)

print("[CONFIG]")
print("min_survivors_floor: 1 (enabled)")
print("rescue_mode: False")
print("min_trades_per_episode: 100 (will kill all)")
print()

try:
    result = run_darwin(
        data=data,
        universe=universe,
        time_config=time_config,
        seed_graph=strategy,
        depth=1,  # Just 1 generation to test mechanism
        branching=2,
        survivors_per_layer=2,
        min_survivors_floor=1,  # ENABLED
        rescue_mode=False,  # DISABLED
        phase3_config=phase3_config,
        run_id="test_survivor_floor",
    )

    floor_triggered = any(
        gen.get('survivor_floor_triggered', False)
        for gen in result.generation_stats
    )

    print()
    print("[RESULT]")
    print(f"Survivor floor triggered: {'YES ✅' if floor_triggered else 'NO ❌'}")
    print(f"Total evaluations: {result.total_evaluations}")

except Exception as e:
    print(f"❌ Test failed with error: {e}")
    import traceback
    traceback.print_exc()

print()
print()

# Test 2: Rescue-from-Best-Dead
print("="*80)
print("TEST 2: RESCUE-FROM-BEST-DEAD")
print("="*80)
print()

print("[CONFIG]")
print("min_survivors_floor: 0 (disabled)")
print("rescue_mode: True")
print("min_trades_per_episode: 100 (will kill all)")
print()

try:
    result = run_darwin(
        data=data,
        universe=universe,
        time_config=time_config,
        seed_graph=strategy,
        depth=1,  # Just 1 generation to test mechanism
        branching=2,
        survivors_per_layer=2,
        min_survivors_floor=0,  # DISABLED
        rescue_mode=True,  # ENABLED
        phase3_config=phase3_config,
        run_id="test_rescue_from_best_dead",
    )

    rescue_triggered = any(
        gen.get('rescue_from_best_dead_triggered', False)
        for gen in result.generation_stats
    )

    print()
    print("[RESULT]")
    print(f"Rescue-from-best-dead triggered: {'YES ✅' if rescue_triggered else 'NO ❌'}")
    print(f"Total evaluations: {result.total_evaluations}")

except Exception as e:
    print(f"❌ Test failed with error: {e}")
    import traceback
    traceback.print_exc()

print()
print()
print("="*80)
print("TESTS COMPLETE")
print("="*80)
print()
print("SUMMARY:")
print("- Survivor floor: Forces top N by fitness even when all killed")
print("- Rescue-from-best-dead: Rescues top 2 by fitness when rescue_mode=True")
print("- Both mechanisms prevent premature evolution termination")
