#!/usr/bin/env python3
"""
Test Phase 3 with a strategy guaranteed to generate trades.
"""

import pandas as pd
from graph.schema import StrategyGraph, Node, UniverseSpec, TimeConfig, DateRange
from validation.evaluation import Phase3Config, evaluate_strategy_phase3
from data.polygon_client import PolygonClient


def make_simple_trading_strategy():
    """Create a strategy that trades frequently: enter when close > open."""
    return StrategyGraph(
        graph_id="simple_trader",
        name="Simple Frequent Trader",
        version="1.0",
        nodes=[
            Node(
                id="market",
                type="MarketData",
                params={},
                inputs={},
            ),
            # Entry: when close > open (should happen ~50% of bars)
            Node(
                id="entry_condition",
                type="Compare",
                params={"op": ">"},
                inputs={"a": ("market", "close"), "b": ("market", "open")},
            ),
            Node(
                id="entry_signal",
                type="EntrySignal",
                params={},
                inputs={"condition": ("entry_condition", "result")},
            ),
            # Exit: when close < open
            Node(
                id="exit_condition",
                type="Compare",
                params={"op": "<"},
                inputs={"a": ("market", "close"), "b": ("market", "open")},
            ),
            Node(
                id="exit_signal",
                type="ExitSignal",
                params={},
                inputs={"condition": ("exit_condition", "result")},
            ),
            # Simple fixed stops/targets
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
            # Fixed position sizing
            Node(
                id="position_size",
                type="PositionSizingFixed",
                params={"dollars": 5000.0},
                inputs={},
            ),
            # Combine into bracket order
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
            # Risk manager - very permissive
            Node(
                id="risk_manager",
                type="RiskManagerDaily",
                params={"max_loss_pct": 0.50, "max_profit_pct": 1.0, "max_trades": 50},
                inputs={"orders": ("bracket", "orders")},
            ),
        ],
        outputs={"orders": ("risk_manager", "filtered_orders")},
        metadata={"test": True},
        universe=UniverseSpec(type="explicit", symbols=["AAPL"]),
        time=TimeConfig(
            timeframe="5m",
            date_range=DateRange(start="2024-10-01", end="2024-12-31"),
        ),
    )


def main():
    print("="*80)
    print("TESTING PHASE 3 WITH GUARANTEED-TO-TRADE STRATEGY")
    print("="*80)
    print()

    # Load data
    print("[DATA LOADING]")
    client = PolygonClient()
    data = client.get_bars("AAPL", "5m", "2024-10-01", "2024-12-31")
    print(f"Loaded {len(data)} bars of AAPL 5m data")

    # Set timestamp as index for Phase 3
    if 'timestamp' in data.columns:
        data = data.set_index('timestamp')
        print("Set timestamp as index for Phase 3 evaluation")
    print()

    # Create simple trading strategy
    strategy = make_simple_trading_strategy()
    print(f"[STRATEGY]")
    print(f"ID: {strategy.graph_id}")
    print(f"Name: {strategy.name}")
    print(f"Entry condition: close > open")
    print(f"Exit condition: close < open")
    print()

    # Phase 3 config with debug enabled
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
        abort_on_all_episode_failures=True,
    )

    print(f"[PHASE 3 CONFIG]")
    print(f"Episodes: {config.n_episodes}")
    print(f"Sampling: {config.sampling_mode}")
    print(f"Min trades per episode: {config.min_trades_per_episode}")
    print()

    # Run evaluation
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
    print(f"Kill reasons: {result.kill_reason}")
    print()

    # Show episode details with debug stats
    phase3 = result.validation_report["phase3"]
    print(f"[EPISODE DETAILS]")
    print(f"Aggregated fitness: {phase3['aggregated_fitness']:.3f}")
    print(f"Median fitness: {phase3['median_fitness']:.3f}")
    print()

    print(f"{'Episode':<10} {'Trades':<8} {'Signals':<10} {'Fills':<8} {'NaN%':<15} {'Fitness':<10}")
    print("-" * 80)
    for ep in phase3["episodes"]:
        label = ep["label"]
        debug = ep.get("debug_stats", {})
        trades = debug.get("fills", 0)
        signals = debug.get("signal_true_count", 0)
        fills = debug.get("fills", 0)
        nan_pct = debug.get("feature_nan_pct", {})
        max_nan = max(nan_pct.values()) if nan_pct else 0
        fitness = ep["fitness"]

        print(f"{label:<10} {trades:<8} {signals:<10} {fills:<8} {max_nan:<15.1f} {fitness:<10.3f}")

    print()
    print(f"[DEBUG STATS SAMPLE - Episode 1]")
    if phase3["episodes"]:
        ep1_debug = phase3["episodes"][0].get("debug_stats", {})
        for key, value in ep1_debug.items():
            print(f"  {key}: {value}")

    print()
    print("="*80)
    print(f"TEST COMPLETE - Strategy {'TRADED' if any(ep.get('debug_stats', {}).get('fills', 0) > 0 for ep in phase3['episodes']) else 'DID NOT TRADE'}")
    print("="*80)


if __name__ == "__main__":
    main()
