#!/usr/bin/env python3
"""
Darwin experiment with guaranteed-to-trade strategy.
"""

import json
from pathlib import Path
from datetime import datetime

from data.polygon_client import PolygonClient
from graph.schema import UniverseSpec, TimeConfig, DateRange, StrategyGraph, Node
from validation.evaluation import Phase3Config
from evolution.darwin import run_darwin


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
print("DARWIN EVOLUTION WITH GUARANTEED-TO-TRADE STRATEGY")
print("="*80)

# Load data
print("\n[DATA LOADING]")
client = PolygonClient()
data = client.get_bars("AAPL", "5m", "2024-10-01", "2024-12-31")
data = data.set_index('timestamp')
print(f"Loaded {len(data)} bars")

# Phase 3 config
phase3_config = Phase3Config(
    enabled=True,
    mode="episodes",
    n_episodes=4,
    min_months=1,
    max_months=2,
    min_bars=50,
    seed=42,
    sampling_mode="stratified_by_regime",
    min_trades_per_episode=1,
    regime_penalty_weight=0.3,
    abort_on_all_episode_failures=True,
)

print(f"\n[PHASE 3 CONFIG]")
print(f"Episodes: {phase3_config.n_episodes}")
print(f"Sampling: {phase3_config.sampling_mode}")

# Universe and time config
universe = UniverseSpec(type="explicit", symbols=["AAPL"])
time_config = TimeConfig(
    timeframe="5m",
    date_range=DateRange(start="2024-10-01", end="2024-12-31"),
)

# Create Adam from our guaranteed trader
adam = make_simple_trading_strategy()

print(f"\n[ADAM STRATEGY]")
print(f"ID: {adam.graph_id}")
print(f"Entry: close > open")

# Run Darwin
print(f"\n{'='*80}")
print("STARTING DARWIN EVOLUTION")
print(f"{'='*80}\n")

result = run_darwin(
    data=data,
    universe=universe,
    time_config=time_config,
    seed_graph=adam,  # Use pre-built strategy
    depth=3,  # 3 generations
    branching=6,  # 6 children per generation
    survivors_per_layer=2,  # Keep top 2
    phase3_config=phase3_config,
    rescue_mode=True,
    run_id="darwin_simple_trader_42",
)

print(f"\n{'='*80}")
print("DARWIN COMPLETE")
print(f"{'='*80}\n")

# Save metadata
metadata_dir = Path("results/experiments/darwin_simple_trader")
metadata_dir.mkdir(parents=True, exist_ok=True)

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
metadata_path = metadata_dir / f"experiment_{timestamp}.json"

metadata = {
    "timestamp": timestamp,
    "config": {
        "depth": 3,
        "branching": 6,
        "survivors": 2,
        "phase3_episodes": 4,
    },
    "run_id": "darwin_simple_trader_42",
}

with open(metadata_path, "w") as f:
    json.dump(metadata, f, indent=2)

print(f"Metadata saved to: {metadata_path}")
print(f"Darwin artifacts: results/runs/darwin_simple_trader_42/")
