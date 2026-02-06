#!/usr/bin/env python3
"""Demo: Natural Language Strategy Compilation

Compiles a natural language strategy description into a StrategyGraph,
validates it, executes it, and evaluates fitness.

Demonstrates Phase 5 NL → StrategyGraph compilation.
"""

import sys
from graph.schema import UniverseSpec, TimeConfig, DateRange
from data.polygon_client import PolygonClient
from llm import compile_nl_to_graph
from validation import evaluate_strategy
import config


def print_section(title: str):
    """Print formatted section header."""
    print("\n" + "=" * 80)
    print(title.center(80))
    print("=" * 80)


def main():
    """Main compilation demo."""
    print_section("NL → STRATEGYGRAPH COMPILATION DEMO")

    # Check API keys
    if not config.POLYGON_API_KEY:
        print("\n❌ ERROR: POLYGON_API_KEY not set")
        sys.exit(1)

    if not config.OPENAI_API_KEY and not config.ANTHROPIC_API_KEY:
        print("\n❌ ERROR: Need OPENAI_API_KEY or ANTHROPIC_API_KEY")
        sys.exit(1)

    # Determine provider
    provider = "openai" if config.OPENAI_API_KEY else "anthropic"
    print(f"\nUsing provider: {provider}")

    # Natural language strategy
    nl_strategy = """
Buy when the 20-period EMA crosses above the 50-period EMA.
Sell when the 20-period EMA crosses below the 50-period EMA.

Use a stop loss at 2x ATR below entry.
Use a take profit at 4x ATR above entry.

Risk $10,000 per trade.
Don't take more than 5 trades per day.
Stop trading if daily loss exceeds 3%.
""".strip()

    # Locked parameters (must not be modified by LLM)
    universe = UniverseSpec(type="explicit", symbols=["AAPL"])
    time_config = TimeConfig(
        timeframe="5m",
        date_range=DateRange(start="2024-10-01", end="2025-01-01")
    )

    print("\n📝 NATURAL LANGUAGE STRATEGY:")
    print("-" * 80)
    print(nl_strategy)
    print("-" * 80)

    print("\n🔒 LOCKED PARAMETERS:")
    print(f"  Universe: {universe.type} - {universe.symbols}")
    print(f"  Timeframe: {time_config.timeframe}")
    print(f"  Date Range: {time_config.date_range.start} to {time_config.date_range.end}")

    # Compile NL to graph
    print_section("COMPILING NL → STRATEGYGRAPH")

    print(f"\n🤖 Calling {provider} to compile strategy...")

    try:
        strategy = compile_nl_to_graph(
            nl_text=nl_strategy,
            universe=universe,
            time_config=time_config,
            provider=provider,
            temperature=0.7,
        )
        print("✓ Compilation successful")
    except Exception as e:
        print(f"❌ Compilation failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # Print compiled graph summary
    print(f"\n📊 COMPILED STRATEGY:")
    print(f"  ID: {strategy.graph_id}")
    print(f"  Name: {strategy.name}")
    print(f"  Nodes: {len(strategy.nodes)}")
    print(f"  Universe: {strategy.universe.type} - {strategy.universe.symbols}")
    print(f"  Timeframe: {strategy.time.timeframe}")

    print(f"\n  Node List:")
    for node in strategy.nodes:
        params_str = ", ".join([f"{k}={v}" for k, v in node.params.items()])
        print(f"    - {node.id:20s} ({node.type:20s}) params: {params_str}")

    # Validate graph structure
    print("\n✓ Validating graph structure...")
    try:
        strategy.validate_structure()
        print("✓ Graph structure valid")
    except Exception as e:
        print(f"❌ Validation failed: {e}")
        sys.exit(1)

    # Fetch data
    print_section("FETCHING DATA & EXECUTING")

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

    # Evaluate strategy
    print("\n🔬 Running full validation suite...")
    print("  (This may take a few minutes...)")

    try:
        result = evaluate_strategy(
            strategy=strategy,
            data=data,
            train_frac=0.75,
            k_windows=6,
            n_jitter=10,
            jitter_pct=0.1,
            initial_capital=100000.0,
        )
        print("✓ Evaluation complete")
    except Exception as e:
        print(f"❌ Evaluation failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # Print results
    print_section("EVALUATION RESULTS")

    print(f"\n  Decision:     {result.decision.upper()}")
    print(f"  Fitness:      {result.fitness:.3f}")

    if result.kill_reason:
        print(f"  Kill Reasons: {', '.join(result.kill_reason)}")

    # Metrics
    report = result.validation_report
    train = report.get('train_metrics', {})
    holdout = report.get('holdout_metrics', {})

    print(f"\n  Train:        Return={train.get('return_pct', 0):.2%}, "
          f"Sharpe={train.get('sharpe', 0):.2f}, "
          f"Trades={train.get('trades', 0)}")

    print(f"  Holdout:      Return={holdout.get('return_pct', 0):.2%}, "
          f"Sharpe={holdout.get('sharpe', 0):.2f}, "
          f"Trades={holdout.get('trades', 0)}")

    failures = report.get('failure_labels', [])
    if failures:
        print(f"  Failures:     {', '.join(failures)}")

    # Show penalties
    penalties = report.get('penalties', {})
    if penalties:
        print(f"\n  Top Penalties:")
        for name, value in sorted(penalties.items(), key=lambda x: x[1], reverse=True)[:3]:
            print(f"    {name:20s} {value:.3f}")

    print_section("DEMO COMPLETE")

    if result.is_survivor():
        print("\n✅ Strategy SURVIVED! Ready for evolution.\n")
    else:
        print(f"\n❌ Strategy KILLED: {', '.join(result.kill_reason)}\n")


if __name__ == "__main__":
    main()
