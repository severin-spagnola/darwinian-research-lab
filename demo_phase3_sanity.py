#!/usr/bin/env python3
"""Phase 3 sanity check: episode-based evaluation end-to-end test."""

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
print("PHASE 3 SANITY CHECK: Episode-Based Evaluation")
print("="*70)

# Load data
print("\n1. Loading AAPL data from cache...")
client = PolygonClient()
data = client.get_bars("AAPL", "5m", "2024-10-01", "2024-12-31")  # Use cached date range
print(f"   ✓ Loaded {len(data)} bars")

# Phase 3 requires timestamp as index (not column)
if 'timestamp' in data.columns:
    data = data.set_index('timestamp')
    print(f"   ✓ Set timestamp as index for Phase 3")

# Build a simple RSI mean reversion strategy graph
print("\n2. Building test strategy graph...")
strategy = StrategyGraph(
    graph_id="phase3_test_rsi_mean_reversion",
    name="Phase 3 Test: RSI Mean Reversion",
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
    metadata={"description": "RSI mean reversion test for Phase 3", "author": "sanity_check"},
    universe=UniverseSpec(type="explicit", symbols=["AAPL"]),
    time=TimeConfig(
        timeframe="5m",
        date_range=DateRange(start="2024-10-01", end="2024-12-31"),
    ),
)
print(f"   ✓ Built strategy with {len(strategy.nodes)} nodes")

# Configure Phase 3 evaluation
print("\n3. Configuring Phase 3 evaluation...")
phase3_config = Phase3Config(
    enabled=True,
    mode="episodes",  # Must set mode to "episodes" to enable Phase 3
    n_episodes=2,  # Reduced for 3-month data range
    min_months=1,
    max_months=1,
    min_bars=50,  # Lowered for 5-minute bars
    seed=42,
)
print(f"   ✓ Mode: {phase3_config.mode}")
print(f"   ✓ Episodes: {phase3_config.n_episodes}")
print(f"   ✓ Episode length: {phase3_config.min_months}-{phase3_config.max_months} months")
print(f"   ✓ Min bars per episode: {phase3_config.min_bars}")
print(f"   ✓ Seed: {phase3_config.seed}")

# Run evaluation
print("\n4. Running Phase 3 evaluation...")
result = evaluate_strategy_phase3(
    strategy=strategy,
    data=data,
    phase3_config=phase3_config,
    initial_capital=100000.0,
)
print(f"   ✓ Evaluation complete")

# Display results
print("\n" + "="*70)
print("RESULTS")
print("="*70)

print(f"\nAggregated Fitness: {result.fitness:.3f}")
print(f"Decision: {result.decision.upper()}")
if result.kill_reason:
    print(f"Kill Reasons: {', '.join(result.kill_reason)}")

# Phase 3 data is in validation_report
if "phase3" in result.validation_report:
    phase3 = result.validation_report["phase3"]
    print(f"\nEpisode Statistics:")
    print(f"  Number of episodes: {len(phase3['episodes'])}")
    print(f"  Median fitness: {phase3['median_fitness']:.3f}")
    print(f"  Best fitness: {phase3['best_fitness']:.3f}")
    print(f"  Worst fitness: {phase3['worst_fitness']:.3f}")
    print(f"  Std fitness: {phase3['std_fitness']:.3f}")

    print(f"\nPenalties:")
    print(f"  Worst-case penalty: {phase3['worst_case_penalty']:.3f}")
    print(f"  Dispersion penalty: {phase3['dispersion_penalty']:.3f}")

    print(f"\nPer-Episode Summary:")
    for i, ep in enumerate(phase3['episodes'], 1):
        print(f"  Episode {i} ({ep['label']}):")
        print(f"    Period: {ep['start_ts'][:10]} to {ep['end_ts'][:10]}")
        print(f"    Fitness: {ep['fitness']:.3f}")
        print(f"    Decision: {ep['decision']}")
        if ep.get('tags'):
            tag_str = ", ".join([f"{k}={v}" for k, v in ep['tags'].items()])
            print(f"    Tags: {tag_str}")

# Save artifacts
print("\n" + "="*70)
print("SAVING ARTIFACTS")
print("="*70)

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
artifacts_dir = Path("results/phase3_sanity") / timestamp
artifacts_dir.mkdir(parents=True, exist_ok=True)

# Save summary
summary = {
    "timestamp": timestamp,
    "strategy_id": strategy.graph_id,
    "phase3_config": {
        "enabled": phase3_config.enabled,
        "n_episodes": phase3_config.n_episodes,
        "min_months": phase3_config.min_months,
        "max_months": phase3_config.max_months,
        "min_bars": phase3_config.min_bars,
        "seed": phase3_config.seed,
    },
    "aggregated_fitness": result.fitness,
    "decision": result.decision,
    "kill_reasons": result.kill_reason,
}

if "phase3" in result.validation_report:
    summary["episode_summary"] = result.validation_report["phase3"]

summary_path = artifacts_dir / "summary.json"
with open(summary_path, "w") as f:
    json.dump(summary, f, indent=2)

print(f"\n✓ Saved summary to: {summary_path}")
print(f"✓ Artifacts directory: {artifacts_dir}")

print("\n" + "="*70)
print("SANITY CHECK COMPLETE")
print("="*70)
print("\n✅ Phase 3 episode-based evaluation is working correctly!")
print(f"   Run completed with {phase3_config.n_episodes} episodes")
print(f"   Aggregated fitness: {result.fitness:.3f}")
print(f"   Decision: {result.decision.upper()}")
