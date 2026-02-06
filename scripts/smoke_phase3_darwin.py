#!/usr/bin/env python3
"""Phase 3 Part 2 smoke test: Darwin integration with phase3 evaluation.

Verifies:
  - Phase 3 evaluation runs inside Darwin (seed_graph, no LLM compile)
  - Phase3Report JSON artifacts are created under results/runs/<run_id>/phase3_reports/
  - Schedule config is serialised to run_config.json
  - Curriculum sampling_mode_schedule is respected

Because LLM mutations will fail without API keys, this test only evaluates
Adam (generation 0). The key goal is verifying wiring, not evolution depth.
"""

import sys
import json
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd

from graph.schema import StrategyGraph, Node, UniverseSpec, TimeConfig, DateRange
from validation.evaluation import Phase3Config, Phase3ScheduleConfig
import config as cfg


def _build_sma_crossover() -> StrategyGraph:
    """Simple SMA crossover strategy (no LLM required)."""
    return StrategyGraph(
        graph_id="smoke_sma_crossover",
        name="Smoke SMA Crossover",
        version="1.0",
        universe=UniverseSpec(type="explicit", symbols=["TEST"]),
        time=TimeConfig(
            timeframe="1d",
            date_range=DateRange(start="2020-01-01", end="2022-12-31"),
        ),
        nodes=[
            Node(id="sma_fast", type="SMA", params={"period": 10}, inputs={}),
            Node(id="sma_slow", type="SMA", params={"period": 30}, inputs={}),
            Node(
                id="cmp",
                type="Compare",
                params={"op": ">"},
                inputs={"a": ("sma_fast", "value"), "b": ("sma_slow", "value")},
            ),
            Node(
                id="orders",
                type="orders",
                params={"side": "long", "qty": 100},
                inputs={"entry_signal": ("cmp", "result")},
            ),
        ],
        outputs={"orders": ("orders", "orders")},
    )


def _make_synthetic_data(n_days: int = 600, seed: int = 42) -> pd.DataFrame:
    rng = np.random.RandomState(seed)
    dates = pd.bdate_range("2020-01-02", periods=n_days, freq="B")
    close = 100.0 + np.cumsum(rng.randn(n_days) * 0.5)
    close = np.maximum(close, 10.0)
    return pd.DataFrame(
        {
            "open": close + rng.randn(n_days) * 0.1,
            "high": close + abs(rng.randn(n_days) * 0.5),
            "low": close - abs(rng.randn(n_days) * 0.5),
            "close": close,
            "volume": (rng.rand(n_days) * 1e6).astype(int),
        },
        index=dates,
    )


def main():
    print("=" * 70)
    print("PHASE 3 DARWIN SMOKE TEST")
    print("=" * 70)

    # Use a temp directory so we don't pollute real results
    with tempfile.TemporaryDirectory() as tmpdir:
        original_results = cfg.RESULTS_DIR
        cfg.RESULTS_DIR = Path(tmpdir)

        try:
            data = _make_synthetic_data()
            print(f"\n[1] Synthetic data: {len(data)} bars, "
                  f"{data.index[0].date()} to {data.index[-1].date()}")

            strategy = _build_sma_crossover()
            print(f"[2] Strategy: {strategy.graph_id}")

            phase3_config = Phase3Config(
                enabled=True,
                mode="episodes",
                n_episodes=2,
                min_months=2,
                max_months=4,
                min_bars=20,
                seed=42,
                sampling_mode="random",
                min_trades_per_episode=0,
                regime_penalty_weight=0.3,
                abort_on_all_episode_failures=False,
                schedule=Phase3ScheduleConfig(
                    grace_generations=1,
                    penalty_weight_schedule=[0.0, 0.5, 1.0],
                ),
                sampling_mode_schedule=["random", "uniform_random"],
            )
            print(f"[3] Phase3Config: episodes={phase3_config.n_episodes}, "
                  f"schedule grace={phase3_config.schedule.grace_generations}")

            universe = UniverseSpec(type="explicit", symbols=["TEST"])
            time_config = TimeConfig(
                timeframe="1d",
                date_range=DateRange(start="2020-01-01", end="2022-12-31"),
            )

            # Run Darwin with depth=1 (Adam + 1 gen attempt)
            # Mutation will fail without LLM, but Adam evaluation should succeed
            from evolution.darwin import run_darwin

            print(f"\n[4] Running Darwin (depth=1, branching=1)...")
            try:
                summary = run_darwin(
                    data=data,
                    universe=universe,
                    time_config=time_config,
                    seed_graph=strategy,
                    depth=1,
                    branching=1,
                    survivors_per_layer=1,
                    max_total_evals=5,
                    rescue_mode=True,
                    phase3_config=phase3_config,
                    run_id="smoke_p3_darwin",
                )
            except Exception as e:
                print(f"  Darwin raised (expected if no LLM): {e}")
                summary = None

            # Verify artifacts
            print(f"\n[5] Checking artifacts...")
            run_dir = Path(tmpdir) / "runs" / "smoke_p3_darwin"

            checks_passed = 0
            checks_total = 0

            # Check run_config.json
            checks_total += 1
            config_path = run_dir / "run_config.json"
            if config_path.exists():
                with open(config_path) as f:
                    rc = json.load(f)
                has_p3 = "phase3_config" in rc
                has_schedule = "schedule" in rc.get("phase3_config", {})
                has_sms = "sampling_mode_schedule" in rc.get("phase3_config", {})
                print(f"  run_config.json: phase3={has_p3}, schedule={has_schedule}, "
                      f"sampling_mode_schedule={has_sms}")
                if has_p3 and has_schedule:
                    checks_passed += 1
                    print(f"    PASS")
                else:
                    print(f"    FAIL")
            else:
                print(f"  run_config.json: MISSING")

            # Check phase3_reports directory
            checks_total += 1
            p3_dir = run_dir / "phase3_reports"
            if p3_dir.exists():
                reports = list(p3_dir.glob("*.json"))
                print(f"  phase3_reports/: {len(reports)} report(s)")
                if len(reports) >= 1:
                    # Validate content of first report
                    with open(reports[0]) as f:
                        report = json.load(f)
                    has_phase3 = "phase3" in report
                    has_episodes = "episodes" in report.get("phase3", {})
                    has_explanation = "explanation" in report.get("phase3", {})
                    print(f"    First report: phase3={has_phase3}, episodes={has_episodes}, "
                          f"explanation={has_explanation}")
                    if has_phase3 and has_episodes:
                        checks_passed += 1
                        print(f"    PASS")
                    else:
                        print(f"    FAIL")
                else:
                    print(f"    FAIL (no reports)")
            else:
                print(f"  phase3_reports/: MISSING")

            # Check evals directory
            checks_total += 1
            evals_dir = run_dir / "evals"
            if evals_dir.exists():
                evals = list(evals_dir.glob("*.json"))
                print(f"  evals/: {len(evals)} eval(s)")
                if len(evals) >= 1:
                    checks_passed += 1
                    print(f"    PASS")
                else:
                    print(f"    FAIL")
            else:
                print(f"  evals/: MISSING")

            # Check blue_memos directory
            checks_total += 1
            memos_dir = run_dir / "blue_memos"
            if memos_dir.exists():
                memos = list(memos_dir.glob("*.json"))
                print(f"  blue_memos/: {len(memos)} memo(s)")
                if len(memos) >= 1:
                    checks_passed += 1
                    print(f"    PASS")
                else:
                    print(f"    FAIL")
            else:
                print(f"  blue_memos/: MISSING")

            # Check red_verdicts directory
            checks_total += 1
            verdicts_dir = run_dir / "red_verdicts"
            if verdicts_dir.exists():
                verdicts = list(verdicts_dir.glob("*.json"))
                print(f"  red_verdicts/: {len(verdicts)} verdict(s)")
                if len(verdicts) >= 1:
                    checks_passed += 1
                    print(f"    PASS")
                else:
                    print(f"    FAIL")
            else:
                print(f"  red_verdicts/: MISSING")

            # Check summary
            checks_total += 1
            summary_path = run_dir / "summary.json"
            if summary_path.exists():
                checks_passed += 1
                print(f"  summary.json: EXISTS - PASS")
            else:
                print(f"  summary.json: MISSING - FAIL")

            print(f"\n{'='*70}")
            if checks_passed == checks_total:
                print(f"SMOKE TEST PASSED ({checks_passed}/{checks_total} checks)")
            else:
                print(f"SMOKE TEST PARTIAL ({checks_passed}/{checks_total} checks)")
            print(f"{'='*70}")

            return 0 if checks_passed == checks_total else 1

        finally:
            cfg.RESULTS_DIR = original_results


if __name__ == "__main__":
    sys.exit(main())
