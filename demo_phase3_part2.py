#!/usr/bin/env python3
"""Phase 3 Part 2 demo: stratified sampling and regime robustness."""

import json
from pathlib import Path
from datetime import datetime

from data.polygon_client import PolygonClient
from graph.schema import (
    StrategyGraph,
    Node,
    UniverseSpec,
    TimeConfig,
    DateRange,
)
from validation.evaluation import Phase3Config, evaluate_strategy_phase3

print("="*70)
print("PHASE 3 PART 2 DEMO: Stratified Sampling & Regime Robustness")
print("="*70)

# Load data
print("\n1. Loading AAPL data from cache...")
client = PolygonClient()
data = client.get_bars("AAPL", "5m", "2024-10-01", "2024-12-31")
print(f"   ✓ Loaded {len(data)} bars")

# Phase 3 requires timestamp as index (not column)
if 'timestamp' in data.columns:
    data = data.set_index('timestamp')
    print(f"   ✓ Set timestamp as index for Phase 3")

# Build a simple RSI mean reversion strategy graph
print("\n2. Building test strategy graph...")
strategy = StrategyGraph(
    graph_id="phase3_part2_rsi_mean_reversion",
    name="Phase 3 Part 2 Test: RSI Mean Reversion",
    version="1.0",
    nodes=[
        Node(
            id="market",
            type="MarketData",
            params={},
            inputs={},
        ),
        Node(
            id="rsi",
            type="RSI",
            params={"period": 14},
            inputs={"series": ("market", "close")},
        ),
        Node(
            id="const_30",
            type="Constant",
            params={"value": 30.0},
            inputs={},
        ),
        Node(
            id="const_70",
            type="Constant",
            params={"value": 70.0},
            inputs={},
        ),
        Node(
            id="entry_compare",
            type="Compare",
            params={"op": "<"},
            inputs={"a": ("rsi", "rsi"), "b": ("const_30", "value")},
        ),
        Node(
            id="exit_compare",
            type="Compare",
            params={"op": ">"},
            inputs={"a": ("rsi", "rsi"), "b": ("const_70", "value")},
        ),
        Node(
            id="entry_signal",
            type="EntrySignal",
            params={},
            inputs={"condition": ("entry_compare", "result")},
        ),
        Node(
            id="exit_signal",
            type="ExitSignal",
            params={},
            inputs={"condition": ("exit_compare", "result")},
        ),
        Node(
            id="stop_fixed",
            type="StopLossFixed",
            params={"points": 2.0},
            inputs={},
        ),
        Node(
            id="tp_fixed",
            type="TakeProfitFixed",
            params={"points": 5.0},
            inputs={},
        ),
        Node(
            id="position_size",
            type="PositionSizingFixed",
            params={"dollars": 1000.0},
            inputs={},
        ),
        Node(
            id="bracket",
            type="BracketOrder",
            params={},
            inputs={
                "entry_signal": ("entry_signal", "signal"),
                "exit_signal": ("exit_signal", "signal"),
                "stop_config": ("stop_fixed", "stop_config"),
                "tp_config": ("tp_fixed", "tp_config"),
                "size_config": ("position_size", "size_config"),
            },
        ),
        Node(
            id="risk_manager",
            type="RiskManagerDaily",
            params={"max_loss_pct": 0.02, "max_profit_pct": 0.10, "max_trades": 5},
            inputs={"orders": ("bracket", "orders")},
        ),
    ],
    outputs={"orders": ("risk_manager", "filtered_orders")},
    metadata={"description": "RSI mean reversion test for Phase 3 Part 2", "author": "demo"},
    universe=UniverseSpec(type="explicit", symbols=["AAPL"]),
    time=TimeConfig(
        timeframe="5m",
        date_range=DateRange(start="2024-10-01", end="2024-12-31"),
    ),
)
print(f"   ✓ Built strategy with {len(strategy.nodes)} nodes")

# Demo 1: Random sampling (baseline)
print("\n3a. Running Phase 3 with RANDOM sampling...")
phase3_random = Phase3Config(
    enabled=True,
    mode="episodes",
    n_episodes=3,
    min_months=1,
    max_months=1,
    min_bars=50,
    seed=42,
    sampling_mode="random",
    min_trades_per_episode=3,
    regime_penalty_weight=0.3,
)
print(f"   ✓ Mode: {phase3_random.mode}")
print(f"   ✓ Sampling: {phase3_random.sampling_mode}")
print(f"   ✓ Episodes: {phase3_random.n_episodes}")

result_random = evaluate_strategy_phase3(
    strategy=strategy,
    data=data,
    phase3_config=phase3_random,
    initial_capital=100000.0,
)
print(f"   ✓ Evaluation complete")

# Demo 2: Stratified sampling (new feature)
print("\n3b. Running Phase 3 with STRATIFIED sampling...")
phase3_stratified = Phase3Config(
    enabled=True,
    mode="episodes",
    n_episodes=3,
    min_months=1,
    max_months=1,
    min_bars=50,
    seed=42,
    sampling_mode="stratified_by_regime",
    min_trades_per_episode=3,
    regime_penalty_weight=0.3,
)
print(f"   ✓ Mode: {phase3_stratified.mode}")
print(f"   ✓ Sampling: {phase3_stratified.sampling_mode}")
print(f"   ✓ Episodes: {phase3_stratified.n_episodes}")

result_stratified = evaluate_strategy_phase3(
    strategy=strategy,
    data=data,
    phase3_config=phase3_stratified,
    initial_capital=100000.0,
)
print(f"   ✓ Evaluation complete")

# Display comparison
print("\n" + "="*70)
print("COMPARISON: RANDOM vs STRATIFIED")
print("="*70)

print("\n[RANDOM SAMPLING]")
print(f"Aggregated Fitness: {result_random.fitness:.3f}")
print(f"Decision: {result_random.decision.upper()}")

if "phase3" in result_random.validation_report:
    phase3_random_data = result_random.validation_report["phase3"]
    print(f"\nEpisode Statistics:")
    print(f"  Median fitness: {phase3_random_data['median_fitness']:.3f}")
    print(f"  Best fitness: {phase3_random_data['best_fitness']:.3f}")
    print(f"  Worst fitness: {phase3_random_data['worst_fitness']:.3f}")
    print(f"  Std fitness: {phase3_random_data['std_fitness']:.3f}")

    print(f"\nPenalties:")
    print(f"  Worst-case: {phase3_random_data['worst_case_penalty']:.3f}")
    print(f"  Dispersion: {phase3_random_data['dispersion_penalty']:.3f}")
    print(f"  Single-regime: {phase3_random_data['single_regime_penalty']:.3f}")

    print(f"\nRegime Coverage:")
    coverage = phase3_random_data['regime_coverage']
    print(f"  Unique regimes: {coverage['unique_regimes']}")
    print(f"  Regime distribution:")
    for regime_str, count in coverage['regime_counts'].items():
        print(f"    {regime_str}: {count} episodes")

print("\n" + "-"*70)

print("\n[STRATIFIED SAMPLING]")
print(f"Aggregated Fitness: {result_stratified.fitness:.3f}")
print(f"Decision: {result_stratified.decision.upper()}")

if "phase3" in result_stratified.validation_report:
    phase3_stratified_data = result_stratified.validation_report["phase3"]
    print(f"\nEpisode Statistics:")
    print(f"  Median fitness: {phase3_stratified_data['median_fitness']:.3f}")
    print(f"  Best fitness: {phase3_stratified_data['best_fitness']:.3f}")
    print(f"  Worst fitness: {phase3_stratified_data['worst_fitness']:.3f}")
    print(f"  Std fitness: {phase3_stratified_data['std_fitness']:.3f}")

    print(f"\nPenalties:")
    print(f"  Worst-case: {phase3_stratified_data['worst_case_penalty']:.3f}")
    print(f"  Dispersion: {phase3_stratified_data['dispersion_penalty']:.3f}")
    print(f"  Single-regime: {phase3_stratified_data['single_regime_penalty']:.3f}")

    print(f"\nRegime Coverage:")
    coverage = phase3_stratified_data['regime_coverage']
    print(f"  Unique regimes: {coverage['unique_regimes']}")
    print(f"  Regime distribution:")
    for regime_str, count in coverage['regime_counts'].items():
        print(f"    {regime_str}: {count} episodes")

    print(f"\nPer-Episode Details:")
    for ep in phase3_stratified_data['episodes']:
        print(f"  {ep['label']}: fitness={ep['fitness']:.3f}, regime={ep['tags']}")

# Save artifacts
print("\n" + "="*70)
print("SAVING ARTIFACTS")
print("="*70)

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
artifacts_dir = Path("results/phase3_part2") / timestamp
artifacts_dir.mkdir(parents=True, exist_ok=True)

# Save comparison summary
comparison = {
    "timestamp": timestamp,
    "strategy_id": strategy.graph_id,
    "random_sampling": {
        "fitness": result_random.fitness,
        "decision": result_random.decision,
        "phase3_data": result_random.validation_report.get("phase3", {}),
    },
    "stratified_sampling": {
        "fitness": result_stratified.fitness,
        "decision": result_stratified.decision,
        "phase3_data": result_stratified.validation_report.get("phase3", {}),
    },
}

summary_path = artifacts_dir / "comparison.json"
with open(summary_path, "w") as f:
    json.dump(comparison, f, indent=2)

print(f"\n✓ Saved comparison to: {summary_path}")
print(f"✓ Artifacts directory: {artifacts_dir}")

print("\n" + "="*70)
print("DEMO COMPLETE")
print("="*70)
print("\n✅ Phase 3 Part 2 features demonstrated successfully!")
print(f"   Random fitness: {result_random.fitness:.3f}")
print(f"   Stratified fitness: {result_stratified.fitness:.3f}")
print(f"   Stratified sampling aims for better regime coverage")
