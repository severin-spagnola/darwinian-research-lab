#!/usr/bin/env python3
"""
Test rescue-from-best-dead mechanism.
When rescue_mode=True and survivor_floor=0, should rescue top N by fitness.
"""

import pandas as pd
from graph.schema import StrategyGraph, Node, UniverseSpec, TimeConfig, DateRange
from validation.evaluation import Phase3Config
from evolution.darwin import run_darwin
from data.polygon_client import PolygonClient


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
        universe=UniverseSpec(type="explicit", symbols=["AAPL"]),
        time=TimeConfig(
            timeframe="5m",
            date_range=DateRange(start="2024-10-01", end="2024-12-31"),
        ),
    )


print("="*80)
print("TESTING RESCUE-FROM-BEST-DEAD MECHANISM")
print("="*80)
print()

# Load data
print("[DATA LOADING]")
client = PolygonClient()
data = client.get_bars("AAPL", "5m", "2024-10-01", "2024-12-31")
data = data.set_index('timestamp')
print(f"Loaded {len(data)} bars")
print()

# Create strategy
strategy = make_simple_trading_strategy()

# Phase 3 config with VERY HIGH min_trades requirement to kill all strategies
phase3_config = Phase3Config(
    enabled=True,
    mode="episodes",
    n_episodes=3,
    min_months=1,
    max_months=2,
    min_bars=50,
    seed=42,
    sampling_mode="stratified_by_regime",
    min_trades_per_episode=100,  # Unreasonably high - will kill all
    regime_penalty_weight=0.3,
    abort_on_all_episode_failures=False,
)

print("[PHASE 3 CONFIG]")
print(f"Min trades per episode: {phase3_config.min_trades_per_episode} (very high - will kill all)")
print()

# Universe and time config
universe = UniverseSpec(type="explicit", symbols=["AAPL"])
time_config = TimeConfig(
    timeframe="5m",
    date_range=DateRange(start="2024-10-01", end="2024-12-31"),
)

print("[DARWIN CONFIG]")
print("rescue_mode: True")
print("min_survivors_floor: 0 (disabled - forcing rescue-from-best-dead)")
print("depth: 2 generations")
print("branching: 3 children per parent")
print()

# Run Darwin with rescue mode enabled but survivor floor disabled
print("="*80)
print("RUNNING DARWIN")
print("="*80)
print()

result = run_darwin(
    data=data,
    universe=universe,
    time_config=time_config,
    seed_graph=strategy,
    depth=2,
    branching=3,
    survivors_per_layer=2,
    min_survivors_floor=0,  # DISABLED - force rescue-from-best-dead
    rescue_mode=True,  # ENABLED
    phase3_config=phase3_config,
    run_id="test_rescue_from_best_dead",
)

print()
print("="*80)
print("RESULTS")
print("="*80)
print()

print(f"Total evaluations: {result.total_evaluations}")
print(f"Generations completed: {len(result.generation_stats)}")
print()

# Check if rescue-from-best-dead was triggered
rescue_triggered = any(
    gen.get('rescue_from_best_dead_triggered', False)
    for gen in result.generation_stats
)

print("[RESCUE-FROM-BEST-DEAD CHECK]")
print(f"Rescue triggered: {'YES' if rescue_triggered else 'NO'}")
print()

if rescue_triggered:
    print("✅ TEST PASSED: Rescue-from-best-dead mechanism triggered when survivor_floor=0 and rescue_mode=True")
    print()
    print("[GENERATION SUMMARY]")
    for gen_stats in result.generation_stats:
        gen = gen_stats.get('generation')
        rescue = gen_stats.get('rescue_from_best_dead_triggered', False)
        survivors = gen_stats.get('survivors', 0)
        print(f"Gen {gen}: survivors={survivors}, rescue={rescue}")
else:
    print("❌ TEST FAILED: Rescue-from-best-dead did not trigger")
    print()
    print("[GENERATION SUMMARY]")
    for gen_stats in result.generation_stats:
        gen = gen_stats.get('generation')
        floor = gen_stats.get('survivor_floor_triggered', False)
        rescue = gen_stats.get('rescue_from_best_dead_triggered', False)
        survivors = gen_stats.get('survivors', 0)
        print(f"Gen {gen}: survivors={survivors}, floor={floor}, rescue={rescue}")

print()
print("="*80)
print("TEST COMPLETE")
print("="*80)
