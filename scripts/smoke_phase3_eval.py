#!/usr/bin/env python3
"""Phase 3.1 smoke test: prove episode-based evaluation works end-to-end.

No LLM calls required. Uses cached Polygon data for AAPL 5m or synthetic
data as fallback. Deterministic via fixed seed.
"""

import sys
from pathlib import Path

# Allow running from repo root or scripts/
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd

from graph.schema import StrategyGraph, Node, UniverseSpec, TimeConfig, DateRange
from validation.evaluation import Phase3Config, evaluate_strategy_phase3


def _build_rsi_mean_reversion() -> StrategyGraph:
    """Hardcoded RSI mean-reversion strategy (no LLM)."""
    return StrategyGraph(
        graph_id="smoke_rsi_mean_reversion",
        name="Smoke Test: RSI Mean Reversion",
        version="1.0",
        universe=UniverseSpec(type="explicit", symbols=["AAPL"]),
        time=TimeConfig(
            timeframe="5m",
            date_range=DateRange(start="2024-10-01", end="2025-01-01"),
        ),
        nodes=[
            Node(id="market", type="MarketData", params={}, inputs={}),
            Node(id="rsi", type="RSI", params={"period": 14},
                 inputs={"series": ("market", "close")}),
            Node(id="const_30", type="Constant", params={"value": 30.0}, inputs={}),
            Node(id="const_70", type="Constant", params={"value": 70.0}, inputs={}),
            Node(id="entry_cmp", type="Compare", params={"op": "<"},
                 inputs={"a": ("rsi", "rsi"), "b": ("const_30", "value")}),
            Node(id="exit_cmp", type="Compare", params={"op": ">"},
                 inputs={"a": ("rsi", "rsi"), "b": ("const_70", "value")}),
            Node(id="entry_signal", type="EntrySignal", params={},
                 inputs={"condition": ("entry_cmp", "result")}),
            Node(id="exit_signal", type="ExitSignal", params={},
                 inputs={"condition": ("exit_cmp", "result")}),
            Node(id="stop_fixed", type="StopLossFixed",
                 params={"points": 2.0}, inputs={}),
            Node(id="tp_fixed", type="TakeProfitFixed",
                 params={"points": 5.0}, inputs={}),
            Node(id="position_size", type="PositionSizingFixed",
                 params={"dollars": 1000.0}, inputs={}),
            Node(id="bracket", type="BracketOrder", params={},
                 inputs={
                     "entry_signal": ("entry_signal", "signal"),
                     "exit_signal": ("exit_signal", "signal"),
                     "stop_config": ("stop_fixed", "stop_config"),
                     "tp_config": ("tp_fixed", "tp_config"),
                     "size_config": ("position_size", "size_config"),
                 }),
            Node(id="risk_manager", type="RiskManagerDaily",
                 params={"max_loss_pct": 0.02, "max_profit_pct": 0.10, "max_trades": 5},
                 inputs={"orders": ("bracket", "orders")}),
        ],
        outputs={"orders": ("risk_manager", "filtered_orders")},
        metadata={"description": "RSI mean reversion smoke test"},
    )


def _load_data() -> pd.DataFrame:
    """Load AAPL 5m data from cache, fall back to synthetic."""
    try:
        from data.polygon_client import PolygonClient
        client = PolygonClient()
        data = client.get_bars("AAPL", "5m", "2024-10-01", "2025-01-01")
        if not data.empty:
            if "timestamp" in data.columns:
                data = data.set_index("timestamp")
            print(f"  Loaded {len(data)} cached AAPL 5m bars")
            return data
    except Exception as e:
        print(f"  Cache unavailable ({e}), using synthetic data")

    # Synthetic fallback: 400 trading days of 5m bars
    rng = np.random.RandomState(42)
    n_bars = 400 * 78  # ~78 five-min bars per trading day
    dates = pd.bdate_range("2024-01-02", periods=400, freq="B")
    timestamps = []
    for d in dates:
        for i in range(78):
            timestamps.append(d + pd.Timedelta(minutes=5 * i + 9 * 60 + 30))

    timestamps = timestamps[:n_bars]
    close = 150.0 + rng.standard_normal(n_bars).cumsum() * 0.3
    close = np.maximum(close, 50.0)

    df = pd.DataFrame({
        "open": close + rng.uniform(-0.2, 0.2, n_bars),
        "high": close + rng.uniform(0.0, 0.5, n_bars),
        "low": close - rng.uniform(0.0, 0.5, n_bars),
        "close": close,
        "volume": rng.randint(1000, 100000, n_bars).astype(float),
    }, index=pd.DatetimeIndex(timestamps))
    print(f"  Generated {len(df)} synthetic bars")
    return df


def main():
    print("=" * 70)
    print("PHASE 3.1 SMOKE TEST")
    print("=" * 70)

    # 1) Load data
    print("\n[1] Loading data...")
    data = _load_data()

    # 2) Build strategy
    print("\n[2] Building RSI mean-reversion strategy...")
    strategy = _build_rsi_mean_reversion()
    print(f"  Graph: {strategy.graph_id} ({len(strategy.nodes)} nodes)")

    # 3) Configure Phase 3
    phase3_config = Phase3Config(
        enabled=True,
        mode="episodes",
        n_episodes=4,
        min_months=1,
        max_months=2,
        min_bars=50,
        seed=42,
        sampling_mode="random",
        min_trades_per_episode=0,  # lenient for smoke test
        regime_penalty_weight=0.3,
        abort_on_all_episode_failures=False,
    )
    print(f"\n[3] Phase3Config: {phase3_config.n_episodes} episodes, "
          f"seed={phase3_config.seed}, mode={phase3_config.sampling_mode}")

    # 4) Run evaluation
    print("\n[4] Running evaluate_strategy_phase3()...")
    result = evaluate_strategy_phase3(
        strategy=strategy,
        data=data,
        phase3_config=phase3_config,
        initial_capital=100000.0,
    )

    # 5) Print results
    print("\n" + "=" * 70)
    print("RESULTS")
    print("=" * 70)
    print(f"  Aggregated fitness : {result.fitness:.4f}")
    print(f"  Decision           : {result.decision.upper()}")
    if result.kill_reason:
        print(f"  Kill reasons       : {', '.join(result.kill_reason)}")

    p3 = result.validation_report.get("phase3", {})
    if p3:
        print(f"\n  Median fitness     : {p3['median_fitness']:.4f}")
        print(f"  Worst fitness      : {p3['worst_fitness']:.4f}")
        print(f"  Best fitness       : {p3['best_fitness']:.4f}")
        print(f"  Std fitness        : {p3['std_fitness']:.4f}")
        print(f"  Worst-case penalty : {p3['worst_case_penalty']:.4f}")
        print(f"  Dispersion penalty : {p3['dispersion_penalty']:.4f}")
        print(f"  Single-regime pen. : {p3['single_regime_penalty']:.4f}")

        rc = p3.get("regime_coverage", {})
        print(f"\n  Unique regimes     : {rc.get('unique_regimes', '?')}")

        print(f"\n  Per-Episode:")
        for i, ep in enumerate(p3.get("episodes", []), 1):
            tags = ep.get("tags", {})
            tag_str = ", ".join(f"{k}={v}" for k, v in tags.items()) if tags else "none"
            err = " [ERROR]" if ep.get("error_details") else ""
            print(f"    Ep {i} ({ep['label']:12s}): "
                  f"fitness={ep['fitness']:+.4f}  "
                  f"decision={ep['decision']:8s}  "
                  f"regime=[{tag_str}]{err}")

        print(f"\n  Trades/episode     : {p3.get('n_trades_per_episode', [])}")

    print("\n" + "=" * 70)
    print("SMOKE TEST PASSED")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
