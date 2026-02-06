#!/usr/bin/env python3
"""Debug strategy execution to see actual errors."""

import json
from pathlib import Path
import traceback

from data.polygon_client import PolygonClient
from graph.schema import StrategyGraph
from validation.evaluation import evaluate_strategy

# Load the compiled strategy
graph_path = Path("results/runs/phase3_exp_42_v3/graphs/momentum_breakout_strategy.json")
with open(graph_path, 'r') as f:
    graph_data = json.load(f)

strategy = StrategyGraph(**graph_data)

# Load data
client = PolygonClient()
data = client.get_bars("AAPL", "5m", "2024-10-01", "2024-12-31")

print(f"Loaded {len(data)} bars")
print(f"Data columns: {data.columns.tolist()}")
print(f"Data index type: {type(data.index)}")
print(f"First few rows:")
print(data.head())

# Try to evaluate with normal data
print("\n" + "="*80)
print("Attempting strategy evaluation (normal data)...")
print("="*80 + "\n")

try:
    result = evaluate_strategy(strategy, data, initial_capital=100000.0)
    print(f"✓ Evaluation succeeded!")
    print(f"  Fitness: {result.fitness}")
    print(f"  Decision: {result.decision}")
    print(f"  Kill reason: {result.kill_reason}")

    if "train" in result.validation_report:
        train = result.validation_report["train"]
        print(f"\n Train metrics:")
        print(f"    Trades: {train.get('n_trades', 0)}")
        print(f"    Total return: {train.get('total_return', 0)}")
        print(f"    Win rate: {train.get('win_rate', 0)}")

except Exception as e:
    print(f"❌ Evaluation FAILED:")
    print(f"   Error type: {type(e).__name__}")
    print(f"   Error message: {str(e)}")
    print(f"\n   Full traceback:")
    traceback.print_exc()

# Now try with timestamp as index (Phase 3 style)
print("\n" + "="*80)
print("Attempting strategy evaluation (timestamp as index - Phase 3 style)...")
print("="*80 + "\n")

if 'timestamp' in data.columns:
    data_indexed = data.set_index('timestamp')
    print(f"Data with timestamp index:")
    print(f"  Index type: {type(data_indexed.index)}")
    print(f"  Columns: {data_indexed.columns.tolist()}")

    try:
        result2 = evaluate_strategy(strategy, data_indexed, initial_capital=100000.0)
        print(f"✓ Evaluation succeeded!")
        print(f"  Fitness: {result2.fitness}")
        print(f"  Decision: {result2.decision}")
        print(f"  Kill reason: {result2.kill_reason}")

        if "train" in result2.validation_report:
            train = result2.validation_report["train"]
            print(f"\n Train metrics:")
            print(f"    Trades: {train.get('n_trades', 0)}")
            print(f"    Total return: {train.get('total_return', 0)}")
            print(f"    Win rate: {train.get('win_rate', 0)}")

    except Exception as e:
        print(f"❌ Evaluation FAILED:")
        print(f"   Error type: {type(e).__name__}")
        print(f"   Error message: {str(e)}")
        print(f"\n   Full traceback:")
        traceback.print_exc()
