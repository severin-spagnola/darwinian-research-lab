#!/usr/bin/env python3
"""Demo: Strategy Validation

Runs SMA crossover strategy through Phase 4 validation suite:
- Train/holdout split
- Subwindow stability analysis
- Parameter jitter testing
- Fitness scoring with penalties
- ValidationReport JSON output
"""

import sys
from datetime import datetime

from graph.schema import StrategyGraph, Node, UniverseSpec, TimeConfig, DateRange
from data.polygon_client import PolygonClient
from validation import run_full_validation, score_validation, create_validation_report
import config


def create_sma_crossover_strategy() -> StrategyGraph:
    """Create SMA crossover strategy for validation."""

    nodes = [
        Node(id="market_data", type="MarketData", params={}, inputs={}),
        Node(
            id="sma_fast",
            type="SMA",
            params={"period": 10},
            inputs={"series": ("market_data", "close")}
        ),
        Node(
            id="sma_slow",
            type="SMA",
            params={"period": 50},
            inputs={"series": ("market_data", "close")}
        ),
        Node(
            id="entry_condition",
            type="Compare",
            params={"op": "cross_up"},
            inputs={"a": ("sma_fast", "sma"), "b": ("sma_slow", "sma")}
        ),
        Node(
            id="exit_condition",
            type="Compare",
            params={"op": "cross_down"},
            inputs={"a": ("sma_fast", "sma"), "b": ("sma_slow", "sma")}
        ),
        Node(
            id="entry_signal",
            type="EntrySignal",
            params={},
            inputs={"condition": ("entry_condition", "result")}
        ),
        Node(
            id="exit_signal",
            type="ExitSignal",
            params={},
            inputs={"condition": ("exit_condition", "result")}
        ),
        Node(
            id="atr",
            type="ATR",
            params={"period": 14},
            inputs={
                "high": ("market_data", "high"),
                "low": ("market_data", "low"),
                "close": ("market_data", "close")
            }
        ),
        Node(
            id="stop_loss",
            type="StopLossATR",
            params={"mult": 1.5},
            inputs={"atr": ("atr", "atr")}
        ),
        Node(
            id="take_profit",
            type="TakeProfitATR",
            params={"mult": 3.0},
            inputs={"atr": ("atr", "atr")}
        ),
        Node(
            id="position_size",
            type="PositionSizingFixed",
            params={"dollars": 10000.0},
            inputs={}
        ),
        Node(
            id="orders",
            type="BracketOrder",
            params={},
            inputs={
                "entry_signal": ("entry_signal", "signal"),
                "exit_signal": ("exit_signal", "signal"),
                "stop_config": ("stop_loss", "stop_config"),
                "tp_config": ("take_profit", "tp_config"),
                "size_config": ("position_size", "size_config")
            }
        ),
        Node(
            id="risk_manager",
            type="RiskManagerDaily",
            params={"max_loss_pct": 0.02, "max_profit_pct": 0.10, "max_trades": 10},
            inputs={"orders": ("orders", "orders")}
        )
    ]

    return StrategyGraph(
        graph_id="sma_crossover_10_50",
        name="SMA Crossover (10/50)",
        version="1.0",
        universe=UniverseSpec(type="explicit", symbols=["AAPL"]),
        time=TimeConfig(
            timeframe="5m",
            date_range=DateRange(start="2024-10-01", end="2025-01-01")
        ),
        nodes=nodes,
        outputs={"orders": ("risk_manager", "filtered_orders")},
        metadata={"description": "SMA crossover validation demo"}
    )


def print_section(title: str):
    """Print a formatted section header."""
    print("\n" + "=" * 70)
    print(title.center(70))
    print("=" * 70)


def main():
    """Main validation demo."""
    print_section("STRATEGY VALIDATION DEMO (PHASE 4)")

    # Check API key
    if not config.POLYGON_API_KEY:
        print("\n❌ ERROR: POLYGON_API_KEY not set")
        sys.exit(1)

    # Create strategy
    print("\n📈 Creating strategy...")
    strategy = create_sma_crossover_strategy()
    strategy.validate_structure()
    print(f"✓ Strategy: {strategy.name} ({strategy.graph_id})")

    # Fetch data
    print("\n📊 Fetching AAPL 5m data (2024-10-01 to 2025-01-01)...")
    client = PolygonClient()

    try:
        data = client.get_bars("AAPL", "5m", "2024-10-01", "2025-01-01")
        print(f"✓ Fetched {len(data)} bars")
    except Exception as e:
        print(f"❌ Data fetch failed: {e}")
        sys.exit(1)

    # Run full validation suite
    print_section("RUNNING VALIDATION SUITE")

    print("\n🔬 Running validation tests...")
    print("  - Train/holdout split (75/25)")
    print("  - Subwindow stability (6 windows)")
    print("  - Parameter jitter (10 runs, ±10%)")

    try:
        validation_results = run_full_validation(
            strategy=strategy,
            data=data,
            train_frac=0.75,
            k_windows=6,
            n_jitter=10,
            jitter_pct=0.1,
            initial_capital=100000.0
        )
        print("✓ Validation complete")
    except Exception as e:
        print(f"❌ Validation failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # Calculate fitness
    print("\n📊 Calculating fitness scores...")
    fitness_results = score_validation(validation_results)
    print("✓ Fitness calculated")

    # Create validation report
    report = create_validation_report(
        strategy_id=strategy.graph_id,
        strategy_name=strategy.name,
        validation_results=validation_results,
        fitness_results=fitness_results
    )

    # Print results
    print_section("VALIDATION RESULTS")

    # Train metrics
    train_m = validation_results['train_results']['metrics']
    print("\n📚 TRAIN SET (75% of data):")
    print(f"  Return:       {train_m['total_return_pct']:>8.2%}")
    print(f"  Sharpe:       {train_m['sharpe_ratio']:>8.2f}")
    print(f"  Max DD:       {train_m['max_drawdown_pct']:>8.2%}")
    print(f"  Trades:       {train_m['trade_count']:>8}")
    print(f"  Win Rate:     {train_m['win_rate']:>8.2%}")

    # Holdout metrics
    holdout_m = validation_results['holdout_results']['metrics']
    print("\n🔒 HOLDOUT SET (25% of data):")
    print(f"  Return:       {holdout_m['total_return_pct']:>8.2%}")
    print(f"  Sharpe:       {holdout_m['sharpe_ratio']:>8.2f}")
    print(f"  Max DD:       {holdout_m['max_drawdown_pct']:>8.2%}")
    print(f"  Trades:       {holdout_m['trade_count']:>8}")
    print(f"  Win Rate:     {holdout_m['win_rate']:>8.2%}")

    # Degradation
    if train_m['total_return_pct'] != 0:
        degradation = (train_m['total_return_pct'] - holdout_m['total_return_pct']) / abs(train_m['total_return_pct'])
        print(f"\n  📉 Degradation: {degradation:.1%}")

    # Stability
    stability = validation_results['stability']
    print("\n📊 STABILITY (6 windows):")
    print(f"  Concentration Penalty: {stability['concentration_penalty']:>6.3f}")
    print(f"  Cliff Penalty:         {stability['cliff_penalty']:>6.3f}")
    print(f"  Consistency Score:     {stability['consistency_score']:>6.3f}")

    # Show window results
    print("\n  Window Performance:")
    for w in stability['window_results']:
        status = "✓" if w.get('error') is None else "✗"
        print(f"    Window {w['window']}: {status} {w['return_pct']:>7.2%} ({w['trades']} trades)")

    # Fragility
    fragility = validation_results['fragility']
    print("\n🔧 PARAMETER FRAGILITY (10 jitter runs, ±10%):")
    print(f"  Return Dispersion:     ${fragility['return_dispersion']:>8,.2f}")
    print(f"  Sign Flip Penalty:     {fragility['sign_flip_penalty']:>6.3f}")
    print(f"  Fragility Score:       {fragility['fragility_score']:>6.3f}")

    # Fitness
    print_section("FITNESS SCORING")

    print(f"\n  Train Score:           {fitness_results['train_score']:>6.3f}")
    print(f"  Holdout Score:         {fitness_results['holdout_score']:>6.3f}")

    print("\n  Penalties:")
    for penalty_name, penalty_value in fitness_results['penalties'].items():
        print(f"    {penalty_name:20s} {penalty_value:>6.3f}")

    print(f"\n  Total Penalty:         {fitness_results['total_penalty']:>6.3f}")
    print(f"\n  🎯 FINAL FITNESS:      {fitness_results['fitness']:>6.3f}")

    # Failure labels
    failure_labels = report.get_failure_labels()
    if failure_labels:
        print(f"\n  ⚠️  Failure Labels: {', '.join(failure_labels)}")
    else:
        print("\n  ✓ No critical failures")

    # Save report
    print_section("SAVING RESULTS")

    report_path = report.save()
    print(f"\n✓ ValidationReport saved to:")
    print(f"  {report_path}")

    print("\n📄 Report JSON preview:")
    print("-" * 70)
    print(report.to_json())
    print("-" * 70)

    print("\n✅ Validation demo complete!\n")


if __name__ == "__main__":
    main()
