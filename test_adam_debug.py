#!/usr/bin/env python3
"""
Evaluate original Adam strategy with debug stats to diagnose no-trade issue.
"""

import json
from compile.openai_compiler import compile_from_nl
from data.polygon_client import PolygonClient
from validation.evaluation import Phase3Config, evaluate_strategy_phase3


def main():
    print("="*80)
    print("DIAGNOSING ORIGINAL ADAM STRATEGY WITH DEBUG STATS")
    print("="*80)
    print()

    # Load data
    print("[DATA LOADING]")
    client = PolygonClient()
    data = client.get_bars("AAPL", "5m", "2024-10-01", "2024-12-31")
    data = data.set_index('timestamp')
    print(f"Loaded {len(data)} bars")
    print()

    # Original Adam prompt
    adam_prompt = """
Create a simple momentum breakout strategy:
- Enter long when price crosses above 20-period SMA
- Exit when price crosses below 20-period SMA
- Use fixed stop loss at 3 points below entry
- Use fixed take profit at 6 points above entry
- Fixed position size of $3000
- Max 5 trades per day
- Only trade between 10am and 3pm
"""

    print("[COMPILING ADAM STRATEGY]")
    print(adam_prompt)

    strategy = compile_from_nl(adam_prompt, provider="openai")
    print(f"Compiled: {strategy.graph_id}")
    print()

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
        abort_on_all_episode_failures=False,  # Don't abort, collect diagnostics
    )

    print("[RUNNING EVALUATION]")
    result = evaluate_strategy_phase3(
        strategy=strategy,
        data=data,
        initial_capital=100000.0,
        phase3_config=config,
    )

    print(f"\n[RESULTS]")
    print(f"Decision: {result.decision}")
    print(f"Fitness: {result.fitness:.3f}")
    print()

    # Show debug stats table
    phase3 = result.validation_report["phase3"]
    print(f"[DEBUG STATS TABLE]")
    print(f"{'Episode':<12} {'Bars':<8} {'Signals':<10} {'Fills':<8} {'Exits':<8} {'NaN%':<10} {'Fitness':<10}")
    print("-" * 90)

    for ep in phase3["episodes"]:
        label = ep["label"]
        debug = ep.get("debug_stats", {})
        bars = debug.get("bars_in_episode", 0)
        signals = debug.get("signal_true_count", 0)
        fills = debug.get("fills", 0)
        exits = debug.get("exits", 0)
        nan_pct = debug.get("feature_nan_pct", {})
        max_nan = max(nan_pct.values()) if nan_pct else 0
        fitness = ep["fitness"]

        print(f"{label:<12} {bars:<8} {signals:<10} {fills:<8} {exits:<8} {max_nan:<10.1f} {fitness:<10.3f}")

    print()
    print(f"[DETAILED DEBUG STATS - Episode 1]")
    if phase3["episodes"]:
        ep1_debug = phase3["episodes"][0].get("debug_stats", {})
        for key, value in ep1_debug.items():
            if key != "feature_nan_pct":  # Skip the verbose one
                print(f"  {key}: {value}")

        if "feature_nan_pct" in ep1_debug and ep1_debug["feature_nan_pct"]:
            print(f"  feature_nan_pct: {ep1_debug['feature_nan_pct']}")

    print()
    print("="*80)
    print(f"DIAGNOSIS: {'TRADES GENERATED' if any(ep.get('debug_stats', {}).get('fills', 0) > 0 for ep in phase3['episodes']) else 'NO TRADES'}")
    print("="*80)

    # Save detailed report
    report_path = "/tmp/adam_debug_report.json"
    with open(report_path, 'w') as f:
        json.dump(result.validation_report, f, indent=2, default=str)
    print(f"\nDetailed report saved to: {report_path}")


if __name__ == "__main__":
    main()
