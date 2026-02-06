#!/usr/bin/env python3
"""
Final Darwin experiment with survivor floor and guaranteed-to-trade Adam.
"""

import json
from pathlib import Path
from datetime import datetime

from data.polygon_client import PolygonClient
from graph.schema import UniverseSpec, TimeConfig, DateRange, StrategyGraph, Node
from validation.evaluation import Phase3Config
from evolution.darwin import run_darwin


def make_guaranteed_trader():
    """Create a strategy guaranteed to trade: close > open."""
    return StrategyGraph(
        graph_id="guaranteed_trader",
        name="Guaranteed Trader (close>open)",
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
        metadata={"experiment": "darwin_final"},
        universe=UniverseSpec(type="explicit", symbols=["AAPL"]),
        time=TimeConfig(
            timeframe="5m",
            date_range=DateRange(start="2024-10-01", end="2024-12-31"),
        ),
    )


print("="*80)
print("DARWIN EVOLUTION - FINAL EXPERIMENT WITH SURVIVOR FLOOR")
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
    n_episodes=6,
    min_months=1,
    max_months=2,
    min_bars=50,
    seed=42,
    sampling_mode="stratified_by_regime",
    min_trades_per_episode=1,
    regime_penalty_weight=0.3,
    abort_on_all_episode_failures=True,
)

print(f"\n[CONFIGURATION]")
print(f"Population: 10 per generation")
print(f"Generations: 5")
print(f"Survivors per layer: 3")
print(f"Min survivors floor: 1 (elitism)")
print(f"Phase 3: {phase3_config.n_episodes} episodes, stratified_by_regime")

# Create Adam
adam = make_guaranteed_trader()

print(f"\n[ADAM STRATEGY]")
print(f"ID: {adam.graph_id}")
print(f"Entry: close > open (guaranteed to generate trades)")

# Universe and time config
universe = UniverseSpec(type="explicit", symbols=["AAPL"])
time_config = TimeConfig(
    timeframe="5m",
    date_range=DateRange(start="2024-10-01", end="2024-12-31"),
)

# Run Darwin
print(f"\n{'='*80}")
print("STARTING DARWIN EVOLUTION")
print(f"{'='*80}\n")

result = run_darwin(
    data=data,
    universe=universe,
    time_config=time_config,
    seed_graph=adam,
    depth=5,  # 5 generations
    branching=10,  # 10 children per parent
    survivors_per_layer=3,  # Keep top 3
    min_survivors_floor=1,  # Force at least 1 survivor
    max_total_evals=200,
    mutate_provider="anthropic",
    rescue_mode=True,
    initial_capital=100000.0,
    run_id="darwin_final_2024",
    phase3_config=phase3_config,
)

print(f"\n{'='*80}")
print("DARWIN EVOLUTION COMPLETE")
print(f"{'='*80}\n")

# Print per-generation summary
print("[PER-GENERATION SUMMARY]")
print(f"{'Gen':<5} {'Best Fitness':<15} {'Median Fitness':<15} {'Survivors':<12} {'Floor?':<10}")
print("-" * 70)

for gen_stats in result.generation_stats:
    gen = gen_stats.get('generation', '?')
    best = gen_stats.get('best_fitness', 0)
    # Calculate median from the generation
    survivors = gen_stats.get('survivors', 0)
    floor_triggered = "YES" if gen_stats.get('survivor_floor_triggered', False) else "no"

    # For median, we'd need to store it - use mean as proxy
    median = gen_stats.get('mean_fitness', 0)

    print(f"{gen:<5} {best:<15.3f} {median:<15.3f} {survivors:<12} {floor_triggered:<10}")

print()
print(f"[FINAL RESULTS]")
print(f"Total evaluations: {result.total_evaluations}")
print(f"Generations completed: {len(result.generation_stats)}")
print(f"Best strategy: {result.best_strategy.graph_id}")
print(f"Best fitness: {result.best_strategy.fitness:.3f}")

# Check if survivor floor was used
floor_used = any(g.get('survivor_floor_triggered', False) for g in result.generation_stats)
print(f"Survivor floor triggered: {'YES' if floor_used else 'NO'}")

# Save metadata
metadata_dir = Path("results/experiments/darwin_final")
metadata_dir.mkdir(parents=True, exist_ok=True)

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
metadata_path = metadata_dir / f"experiment_{timestamp}.json"

metadata = {
    "timestamp": timestamp,
    "config": {
        "depth": 5,
        "branching": 10,
        "survivors": 3,
        "min_survivors_floor": 1,
        "phase3_episodes": 6,
        "phase3_sampling": "stratified_by_regime",
    },
    "results": {
        "total_evaluations": result.total_evaluations,
        "generations_completed": len(result.generation_stats),
        "best_fitness": result.best_strategy.fitness,
        "survivor_floor_used": floor_used,
    },
    "run_id": "darwin_final_2024",
}

with open(metadata_path, "w") as f:
    json.dump(metadata, f, indent=2)

print(f"\n[ARTIFACTS]")
print(f"Metadata: {metadata_path}")
print(f"Run directory: {result.run_dir}")

print(f"\n{'='*80}")
print(f"EXPERIMENT COMPLETE")
print(f"{'='*80}")
