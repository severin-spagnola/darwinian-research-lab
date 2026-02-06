#!/usr/bin/env python3
"""Demo: Darwin Evolution

Runs full Darwin evolution on a natural language strategy.
Evolves through 3 generations with brutal anti-overfitting validation.

This is the complete end-to-end pipeline.
"""

import sys
from graph.schema import UniverseSpec, TimeConfig, DateRange
from data.polygon_client import PolygonClient
from evolution.darwin import run_darwin
import config


def print_section(title: str):
    """Print formatted section header."""
    print("\n" + "=" * 80)
    print(title.center(80))
    print("=" * 80)


def main():
    """Main Darwin evolution demo."""
    print_section("DARWIN EVOLUTION ENGINE")

    # Check API keys
    if not config.POLYGON_API_KEY:
        print("\n❌ ERROR: POLYGON_API_KEY not set")
        sys.exit(1)

    if not config.OPENAI_API_KEY:
        print("\n❌ ERROR: OPENAI_API_KEY needed for compilation")
        sys.exit(1)

    if not config.ANTHROPIC_API_KEY:
        print("\n❌ ERROR: ANTHROPIC_API_KEY needed for mutations")
        sys.exit(1)

    # Natural language strategy
    nl_strategy = """
Trade mean reversion on 5-minute bars.

Entry: Buy when RSI(14) drops below 30 (oversold).
Exit: Sell when RSI rises above 70 (overbought).

Use ATR-based risk management:
- Stop loss: 2x ATR below entry
- Take profit: 3x ATR above entry

Position size: $10,000 per trade
Risk limits: Max 5 trades per day, max 2% daily loss
""".strip()

    print("\n📝 NATURAL LANGUAGE STRATEGY:")
    print("-" * 80)
    print(nl_strategy)
    print("-" * 80)

    # Locked parameters
    universe = UniverseSpec(type="explicit", symbols=["AAPL"])
    time_config = TimeConfig(
        timeframe="5m",
        date_range=DateRange(start="2024-10-01", end="2025-01-01")
    )

    print("\n🔒 LOCKED PARAMETERS:")
    print(f"  Universe:   {universe.symbols}")
    print(f"  Timeframe:  {time_config.timeframe}")
    print(f"  Date Range: {time_config.date_range.start} to {time_config.date_range.end}")

    # Fetch data
    print_section("FETCHING DATA")

    print(f"\n📊 Fetching {universe.symbols[0]} {time_config.timeframe} data...")
    client = PolygonClient()

    try:
        data = client.get_bars(
            symbol=universe.symbols[0],
            timeframe=time_config.timeframe,
            start=time_config.date_range.start,
            end=time_config.date_range.end
        )
        print(f"✓ Fetched {len(data)} bars")
    except Exception as e:
        print(f"❌ Data fetch failed: {e}")
        sys.exit(1)

    # Run Darwin evolution
    print_section("RUNNING DARWIN EVOLUTION")

    print("\n⚙️  Configuration:")
    print(f"  Depth (generations):     3")
    print(f"  Branching (children/parent): 3")
    print(f"  Survivors per layer:     5")
    print(f"  Max total evaluations:   50")
    print(f"  Compile provider:        openai")
    print(f"  Mutate provider:         anthropic")

    print("\n🧬 Starting evolution...")
    print("  (This may take 10-20 minutes...)")

    try:
        summary = run_darwin(
            data=data,
            universe=universe,
            time_config=time_config,
            nl_text=nl_strategy,
            depth=3,
            branching=3,
            survivors_per_layer=5,
            max_total_evals=50,  # Keep low for demo
            compile_provider="openai",
            mutate_provider="anthropic",
            rescue_mode=False,
            initial_capital=100000.0,
        )
    except Exception as e:
        print(f"\n❌ Evolution failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # Print results
    print_section("EVOLUTION RESULTS")

    print(f"\n  Run ID:            {summary.run_id}")
    print(f"  Total Evaluations: {summary.total_evaluations}")

    print(f"\n  🏆 BEST STRATEGY:")
    best = summary.best_strategy
    print(f"      ID:       {best.graph_id}")
    print(f"      Fitness:  {best.fitness:.3f}")
    print(f"      Decision: {best.decision.upper()}")

    if best.validation_report:
        train = best.validation_report.get('train_metrics', {})
        holdout = best.validation_report.get('holdout_metrics', {})
        print(f"      Train:    Return={train.get('return_pct', 0):.2%}, Sharpe={train.get('sharpe', 0):.2f}")
        print(f"      Holdout:  Return={holdout.get('return_pct', 0):.2%}, Sharpe={holdout.get('sharpe', 0):.2f}")

    print(f"\n  📊 TOP 5 STRATEGIES:")
    for i, strategy in enumerate(summary.top_strategies, 1):
        status = "✓" if strategy.is_survivor() else "✗"
        print(f"      {i}. {status} {strategy.graph_id:40s} fitness={strategy.fitness:.3f}")

    print(f"\n  ❌ KILL STATISTICS:")
    if summary.kill_stats:
        for reason, count in list(summary.kill_stats.items())[:5]:
            print(f"      {reason:30s} {count:3d}")
    else:
        print("      No kills!")

    print(f"\n  📈 GENERATION SUMMARY:")
    for gen_stats in summary.generation_stats:
        gen = gen_stats['generation']
        print(f"      Gen {gen}: {gen_stats['survivors']:2d}/{gen_stats['total']:2d} survived, "
              f"best={gen_stats['best_fitness']:.3f}, mean={gen_stats['mean_fitness']:.3f}")

    print_section("ARTIFACTS SAVED")

    print(f"\n  Run directory: {summary.run_dir}")
    print(f"    - run_config.json")
    print(f"    - graphs/*.json ({summary.total_evaluations} graphs)")
    print(f"    - evals/*.json ({summary.total_evaluations} evaluations)")
    print(f"    - lineage.jsonl (parent→child relationships)")
    print(f"    - summary.json (top strategies, kill stats)")

    print_section("DEMO COMPLETE")

    print(f"\n✅ Evolution complete!")
    print(f"   - Evaluated {summary.total_evaluations} strategies")
    print(f"   - Best fitness: {summary.best_strategy.fitness:.3f}")
    if summary.kill_stats:
        top_kill_reason = list(summary.kill_stats.keys())[0]
        print(f"   - Top kill reason: {top_kill_reason}\n")
    else:
        print(f"   - All strategies survived!\n")


if __name__ == "__main__":
    main()
