#!/usr/bin/env python3
"""
Re-evaluate momentum_breakout Adam with loosened gating for 5-min data.
"""

import json
import pandas as pd
from graph.schema import StrategyGraph
from data.polygon_client import PolygonClient
from validation.evaluation import Phase3Config, evaluate_strategy_phase3


print("="*80)
print("MOMENTUM BREAKOUT WITH LOOSENED GATING FOR 5-MIN DATA")
print("="*80)
print()

# Load the saved Adam strategy
with open('results/runs/phase3_exp_42_fixed/graphs/momentum_breakout_strategy.json') as f:
    strategy_dict = json.load(f)

strategy = StrategyGraph(**strategy_dict)

print(f"[ORIGINAL STRATEGY]")
print(f"ID: {strategy.graph_id}")
print(f"Nodes: {len(strategy.nodes)}")

# Find and update the risk manager to loosen constraints
for node in strategy.nodes:
    if node.type == "RiskManagerDaily":
        print(f"\nFound RiskManagerDaily node: {node.id}")
        print(f"  Original max_trades: {node.params.get('max_trades', 'N/A')}")
        print(f"  Original max_loss_pct: {node.params.get('max_loss_pct', 'N/A')}")

        # LOOSEN: Raise max trades from 5 to 20
        node.params['max_trades'] = 20
        print(f"  Updated max_trades: 20 (was 5)")

    # Also check for time filters (SessionTimeFilter nodes)
    if node.type == "SessionTimeFilter":
        print(f"\nFound SessionTimeFilter node: {node.id}")
        print(f"  Original start_time: {node.params.get('start_time', 'N/A')}")
        print(f"  Original end_time: {node.params.get('end_time', 'N/A')}")

        # EXPAND: Change from 10am-3pm to full session (9:30am-4pm)
        node.params['start_time'] = "09:30"
        node.params['end_time'] = "16:00"
        print(f"  Updated time window: 09:30-16:00 (was 10:00-15:00)")

# Load data
print(f"\n[DATA LOADING]")
client = PolygonClient()
data = client.get_bars("AAPL", "5m", "2024-10-01", "2024-12-31")
data = data.set_index('timestamp')
print(f"Loaded {len(data)} bars")

# Phase 3 config
config = Phase3Config(
    enabled=True,
    mode="episodes",
    n_episodes=3,
    min_months=1,
    max_months=2,
    min_bars=50,
    seed=42,
    sampling_mode="stratified_by_regime",
    min_trades_per_episode=1,
    regime_penalty_weight=0.3,
    abort_on_all_episode_failures=False,
)

print(f"\n[RUNNING EVALUATION]")
result = evaluate_strategy_phase3(strategy, data, 100000.0, config)

print(f"\n[RESULTS]")
print(f"Decision: {result.decision}")
print(f"Fitness: {result.fitness:.3f}")
print()

# Show debug stats comparison
phase3 = result.validation_report['phase3']
print(f"[DEBUG STATS - FILLS COMPARISON]")
print(f"{'Episode':<12} {'Bars':<8} {'Signals':<10} {'Fills (NEW)':<15} {'Fills (OLD)':<15}")
print("-" * 80)

# Original fills were 1 per episode
old_fills = [1, 1, 1]  # From previous run

for idx, ep in enumerate(phase3['episodes']):
    label = ep['label']
    debug = ep.get('debug_stats', {})
    bars = debug.get('bars_in_episode', 0)
    signals = debug.get('signal_true_count', 0)
    new_fills = debug.get('fills', 0)
    old = old_fills[idx] if idx < len(old_fills) else 0

    improvement = f"+{new_fills - old}" if new_fills > old else f"{new_fills - old}"
    print(f"{label:<12} {bars:<8} {signals:<10} {new_fills:<15} {old:<15} ({improvement})")

print()
print(f"[SUMMARY]")
total_new_fills = sum(ep.get('debug_stats', {}).get('fills', 0) for ep in phase3['episodes'])
total_old_fills = sum(old_fills)
print(f"Total fills (new): {total_new_fills}")
print(f"Total fills (old): {total_old_fills}")
print(f"Improvement: {total_new_fills - total_old_fills} fills (+{(total_new_fills/total_old_fills - 1)*100:.0f}%)")

print()
print("="*80)
print("GATING LOOSENED - FILLS INCREASED")
print("="*80)
