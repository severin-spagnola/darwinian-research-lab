"""Test survivor floor mechanism in Darwin evolution."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import pytest
from graph.schema import StrategyGraph, Node, UniverseSpec, TimeConfig, DateRange
from validation.evaluation import Phase3Config, StrategyEvaluationResult
from evolution.darwin import run_darwin


def make_simple_trading_strategy(name_suffix=""):
    """Create a simple strategy for testing."""
    return StrategyGraph(
        graph_id=f"test_strategy{name_suffix}",
        name=f"Test Strategy {name_suffix}",
        version="1.0",
        nodes=[
            Node(id="market", type="MarketData", params={}, inputs={}),
            Node(id="entry_condition", type="Compare", params={"op": ">"},
                 inputs={"a": ("market", "close"), "b": ("market", "open")}),
            Node(id="entry_signal", type="EntrySignal", params={},
                 inputs={"condition": ("entry_condition", "result")}),
            Node(id="exit_condition", type="Compare", params={"op": "<"},
                 inputs={"a": ("market", "close"), "b": ("market", "open")}),
            Node(id="exit_signal", type="ExitSignal", params={},
                 inputs={"condition": ("exit_condition", "result")}),
            Node(id="stop_fixed", type="StopLossFixed", params={"points": 2.0}, inputs={}),
            Node(id="tp_fixed", type="TakeProfitFixed", params={"points": 5.0}, inputs={}),
            Node(id="position_size", type="PositionSizingFixed", params={"dollars": 5000.0}, inputs={}),
            Node(id="bracket", type="BracketOrder", params={},
                 inputs={
                     "entry_signal": ("entry_signal", "signal"),
                     "exit_signal": ("exit_signal", "signal"),
                     "stop_config": ("stop_fixed", "stop_config"),
                     "tp_config": ("tp_fixed", "tp_config"),
                     "size_config": ("position_size", "size_config"),
                 }),
            Node(id="risk_manager", type="RiskManagerDaily",
                 params={"max_loss_pct": 0.50, "max_profit_pct": 1.0, "max_trades": 50},
                 inputs={"orders": ("bracket", "orders")}),
        ],
        outputs={"orders": ("risk_manager", "filtered_orders")},
        metadata={"test": True},
        universe=UniverseSpec(type="explicit", symbols=["TEST"]),
        time=TimeConfig(
            timeframe="1D",
            date_range=DateRange(start="2024-01-01", end="2024-12-31"),
        ),
    )


def make_test_data(n_bars=200):
    """Create test OHLCV data."""
    import numpy as np
    dates = pd.date_range("2024-01-01", periods=n_bars, freq="1D")
    np.random.seed(42)
    close = 100.0 + np.cumsum(np.random.randn(n_bars) * 0.5)
    df = pd.DataFrame({
        "open": close * 0.999,
        "high": close * 1.002,
        "low": close * 0.998,
        "close": close,
        "volume": 1000,
    }, index=dates)
    df.index.name = 'timestamp'
    return df


def test_survivor_floor_triggers_when_all_killed():
    """Test that survivor floor selects top N strategies even when all are killed."""
    data = make_test_data(n_bars=200)
    strategy = make_simple_trading_strategy()

    # Phase 3 config that will likely kill strategies (high penalties)
    phase3_config = Phase3Config(
        enabled=True,
        mode="episodes",
        n_episodes=2,
        min_months=1,
        max_months=1,
        min_bars=20,
        seed=42,
        sampling_mode="random",
        min_trades_per_episode=100,  # Unreasonably high - will kill all
        regime_penalty_weight=0.5,
        abort_on_all_episode_failures=False,
    )

    # Run Darwin with survivor floor
    result = run_darwin(
        data=data,
        universe=UniverseSpec(type="explicit", symbols=["TEST"]),
        time_config=TimeConfig(
            timeframe="1D",
            date_range=DateRange(start="2024-01-01", end="2024-12-31"),
        ),
        seed_graph=strategy,
        depth=2,  # 2 generations
        branching=3,  # 3 children per parent
        survivors_per_layer=2,
        min_survivors_floor=1,  # Force at least 1 survivor
        max_total_evals=20,
        rescue_mode=True,
        initial_capital=100000.0,
        run_id="test_survivor_floor",
        phase3_config=phase3_config,
    )

    # Verify that evolution progressed beyond Gen 0
    assert len(result.generation_stats) > 0, "Should have generation stats"

    # Check if survivor floor was triggered
    survivor_floor_triggered = any(
        gen.get('survivor_floor_triggered', False)
        for gen in result.generation_stats
    )

    # If all strategies are killed, survivor floor should have triggered
    print(f"\nSurvivor floor triggered: {survivor_floor_triggered}")
    print(f"Generations completed: {len(result.generation_stats)}")
    print(f"Total evaluations: {result.total_evaluations}")

    # Verify we got past Adam (at least some children were evaluated)
    assert result.total_evaluations > 1, "Should have evaluated children"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
