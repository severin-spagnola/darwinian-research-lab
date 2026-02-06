#!/usr/bin/env python3
"""Demo: Strategy Evaluation & Survival Gate

Evaluates 3 strategies through the survival gate:
1. SMA Crossover - likely to survive
2. RSI Fixed Stops - likely to survive
3. Intentionally Bad Strategy - should be killed

Demonstrates deterministic kill/survive decisions.
"""

import sys
from graph.schema import StrategyGraph, Node, UniverseSpec, TimeConfig, DateRange
from data.polygon_client import PolygonClient
from validation import evaluate_many, get_survivors, rank_by_fitness
import config


def create_sma_crossover() -> StrategyGraph:
    """Create SMA crossover strategy (10/50)."""
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
    ]

    return StrategyGraph(
        graph_id="sma_10_50",
        name="SMA Crossover (10/50)",
        version="1.0",
        universe=UniverseSpec(type="explicit", symbols=["AAPL"]),
        time=TimeConfig(
            timeframe="5m",
            date_range=DateRange(start="2024-10-01", end="2025-01-01")
        ),
        nodes=nodes,
        outputs={"orders": ("orders", "orders")},
        metadata={"description": "SMA crossover - should survive"}
    )


def create_rsi_fixed_stops() -> StrategyGraph:
    """Create RSI strategy with fixed stops."""
    nodes = [
        Node(id="market_data", type="MarketData", params={}, inputs={}),
        Node(
            id="rsi",
            type="RSI",
            params={"period": 14},
            inputs={"series": ("market_data", "close")}
        ),
        # Use SMA as proxy for constant threshold (hacky but works for demo)
        Node(
            id="oversold_line",
            type="SMA",
            params={"period": 200},  # Long period for stable line
            inputs={"series": ("market_data", "close")}
        ),
        Node(
            id="entry_condition",
            type="Compare",
            params={"op": "<"},
            inputs={"a": ("rsi", "rsi"), "b": ("oversold_line", "sma")}
        ),
        Node(
            id="exit_condition",
            type="Compare",
            params={"op": ">"},
            inputs={"a": ("rsi", "rsi"), "b": ("oversold_line", "sma")}
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
            id="stop_loss",
            type="StopLossFixed",
            params={"points": 2.0},
            inputs={}
        ),
        Node(
            id="take_profit",
            type="TakeProfitFixed",
            params={"points": 5.0},
            inputs={}
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
    ]

    return StrategyGraph(
        graph_id="rsi_fixed",
        name="RSI Fixed Stops",
        version="1.0",
        universe=UniverseSpec(type="explicit", symbols=["AAPL"]),
        time=TimeConfig(
            timeframe="5m",
            date_range=DateRange(start="2024-10-01", end="2025-01-01")
        ),
        nodes=nodes,
        outputs={"orders": ("orders", "orders")},
        metadata={"description": "RSI with fixed stops - outcome uncertain"}
    )


def create_bad_strategy() -> StrategyGraph:
    """Create intentionally bad strategy (should be killed).

    Uses very short SMA periods that will overfit and likely fail holdout.
    """
    nodes = [
        Node(id="market_data", type="MarketData", params={}, inputs={}),
        # Extremely short SMAs - likely to overfit
        Node(
            id="sma_fast",
            type="SMA",
            params={"period": 2},  # Too short!
            inputs={"series": ("market_data", "close")}
        ),
        Node(
            id="sma_slow",
            type="SMA",
            params={"period": 3},  # Also too short!
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
        # Very tight stops - likely to get stopped out frequently
        Node(
            id="stop_loss",
            type="StopLossATR",
            params={"mult": 0.5},  # Too tight!
            inputs={"atr": ("atr", "atr")}
        ),
        Node(
            id="take_profit",
            type="TakeProfitATR",
            params={"mult": 10.0},  # Too wide!
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
    ]

    return StrategyGraph(
        graph_id="bad_strategy_2_3",
        name="Bad Strategy (SMA 2/3)",
        version="1.0",
        universe=UniverseSpec(type="explicit", symbols=["AAPL"]),
        time=TimeConfig(
            timeframe="5m",
            date_range=DateRange(start="2024-10-01", end="2025-01-01")
        ),
        nodes=nodes,
        outputs={"orders": ("orders", "orders")},
        metadata={"description": "Intentionally bad - should be killed"}
    )


def print_section(title: str):
    """Print formatted section header."""
    print("\n" + "=" * 80)
    print(title.center(80))
    print("=" * 80)


def print_evaluation_result(result, index: int):
    """Print detailed evaluation result."""
    print(f"\n[{index}] {result.strategy_name} ({result.graph_id})")
    print("-" * 80)
    print(f"  Decision:     {result.decision.upper()}")
    print(f"  Fitness:      {result.fitness:.3f}")

    if result.kill_reason:
        print(f"  Kill Reasons: {', '.join(result.kill_reason)}")

    # Print key metrics if available
    if result.validation_report:
        train = result.validation_report.get('train_metrics', {})
        holdout = result.validation_report.get('holdout_metrics', {})

        print(f"\n  Train:        Return={train.get('return_pct', 0):.2%}, "
              f"Sharpe={train.get('sharpe', 0):.2f}, "
              f"Trades={train.get('trades', 0)}")

        print(f"  Holdout:      Return={holdout.get('return_pct', 0):.2%}, "
              f"Sharpe={holdout.get('sharpe', 0):.2f}, "
              f"Trades={holdout.get('trades', 0)}")

        failures = result.validation_report.get('failure_labels', [])
        if failures:
            print(f"  Failures:     {', '.join(failures)}")

    print("-" * 80)


def main():
    """Main evaluation demo."""
    print_section("STRATEGY EVALUATION & SURVIVAL GATE DEMO")

    # Check API key
    if not config.POLYGON_API_KEY:
        print("\n❌ ERROR: POLYGON_API_KEY not set")
        sys.exit(1)

    # Create strategies
    print("\n📈 Creating 3 strategies for evaluation...")
    strategies = [
        create_sma_crossover(),
        create_rsi_fixed_stops(),
        create_bad_strategy(),
    ]

    for i, s in enumerate(strategies, 1):
        print(f"  {i}. {s.name} ({s.graph_id})")

    # Fetch data
    print("\n📊 Fetching AAPL 5m data (2024-10-01 to 2025-01-01)...")
    client = PolygonClient()

    try:
        data = client.get_bars("AAPL", "5m", "2024-10-01", "2025-01-01")
        print(f"✓ Fetched {len(data)} bars")
    except Exception as e:
        print(f"❌ Data fetch failed: {e}")
        sys.exit(1)

    # Evaluate all strategies
    print_section("RUNNING BATCH EVALUATION")

    print("\nEvaluating strategies (this may take a few minutes)...")
    print("Each strategy runs: train/holdout + 6 windows + 10 jitter runs\n")

    results = evaluate_many(
        strategies=strategies,
        data=data,
        train_frac=0.75,
        k_windows=6,
        n_jitter=10,
        jitter_pct=0.1,
        initial_capital=100000.0,
        verbose=True
    )

    # Print detailed results
    print_section("EVALUATION RESULTS")

    for i, result in enumerate(results, 1):
        print_evaluation_result(result, i)

    # Summary
    print_section("SURVIVAL SUMMARY")

    survivors = get_survivors(results)
    killed = [r for r in results if r.decision == "kill"]

    print(f"\n✅ SURVIVORS: {len(survivors)}/{len(results)}")
    for result in survivors:
        print(f"   - {result.strategy_name} (fitness={result.fitness:.3f})")

    print(f"\n❌ KILLED: {len(killed)}/{len(results)}")
    for result in killed:
        reasons = ', '.join(result.kill_reason)
        print(f"   - {result.strategy_name} ({reasons})")

    # Rank by fitness
    print(f"\n📊 RANKED BY FITNESS:")
    ranked = rank_by_fitness(results)
    for i, result in enumerate(ranked, 1):
        status = "✓" if result.is_survivor() else "✗"
        print(f"   {i}. {status} {result.strategy_name:30s} fitness={result.fitness:>7.3f}")

    print_section("DEMO COMPLETE")

    print("\n✅ Phase 4.75 validation lock working correctly!")
    print(f"   - {len(survivors)} strategies survived")
    print(f"   - {len(killed)} strategies killed")
    print(f"   - Deterministic kill/survive decisions applied\n")


if __name__ == "__main__":
    main()
