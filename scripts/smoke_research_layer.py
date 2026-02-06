#!/usr/bin/env python3
"""Smoke test for Research Layer integration.

Verifies:
- Blue Memos and Red Verdicts are created during Phase3 evaluation
- Artifacts are saved to correct locations
- No network calls required (mocks You.com client)
"""

import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np

from graph.schema import StrategyGraph, Node, UniverseSpec, TimeConfig, DateRange
from validation.evaluation import Phase3Config, evaluate_strategy_phase3
from research.service import generate_and_save_artifacts
from research.storage import ResearchStorage
from research.youcom import create_research_pack
import config


def _make_synthetic_data(n_days: int = 300, seed: int = 42) -> pd.DataFrame:
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


def _build_test_strategy() -> StrategyGraph:
    return StrategyGraph(
        graph_id="smoke_test_strategy",
        name="Smoke Test Strategy",
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


def main():
    print("=" * 70)
    print("RESEARCH LAYER SMOKE TEST")
    print("=" * 70)

    with tempfile.TemporaryDirectory() as tmpdir:
        original_results = config.RESULTS_DIR
        config.RESULTS_DIR = Path(tmpdir)

        try:
            # Test 1: Create research pack (mocked)
            print("\n[1] Creating research pack (mocked You.com)...")
            mock_client = Mock()
            mock_client.search.return_value = {
                "hits": [
                    {
                        "title": "Mean Reversion Trading",
                        "url": "https://example.com/mr",
                        "snippets": ["Mean reversion strategies assume..."],
                    }
                ]
            }

            pack = create_research_pack(
                "mean reversion strategies", n_results=5, client=mock_client
            )
            print(f"  ✓ Research Pack created: {pack.id}")
            print(f"    Sources: {len(pack.sources)}")
            print(f"    Assumptions: {len(pack.extracted.assumptions)}")

            # Save pack
            storage = ResearchStorage()
            storage.save_research_pack(pack)
            print(f"  ✓ Research Pack saved")

            # Verify pack can be loaded
            loaded_pack = storage.load_research_pack(pack.id)
            assert loaded_pack is not None
            assert loaded_pack.id == pack.id
            print(f"  ✓ Research Pack loaded successfully")

            # Test 2: Run Phase3 evaluation with memo/verdict generation
            print("\n[2] Running Phase3 evaluation with memo/verdict generation...")
            data = _make_synthetic_data()
            strategy = _build_test_strategy()

            phase3_config = Phase3Config(
                enabled=True,
                mode="episodes",
                n_episodes=3,
                min_months=2,
                max_months=3,
                min_bars=20,
                seed=42,
                sampling_mode="random",
                min_trades_per_episode=0,
                regime_penalty_weight=0.3,
                abort_on_all_episode_failures=False,
                generate_memos_verdicts=True,  # Enable research layer
            )

            result = evaluate_strategy_phase3(
                strategy=strategy,
                data=data,
                phase3_config=phase3_config,
                generation=0,
            )

            print(f"  ✓ Evaluation complete: {result.decision.upper()}")
            print(f"    Fitness: {result.fitness:.3f}")

            # Test 3: Generate and save artifacts
            print("\n[3] Generating Blue Memo and Red Verdict...")
            run_id = "smoke_test_run"
            memo, verdict = generate_and_save_artifacts(
                run_id=run_id,
                evaluation_result=result,
                parent_graph_id=None,
                generation=0,
                patch=None,
            )

            print(f"  ✓ Blue Memo created")
            print(f"    Claim: {memo.claim}")
            print(f"    Expected Improvements: {len(memo.expected_improvement)}")
            print(f"    Risks: {len(memo.risks)}")

            print(f"  ✓ Red Verdict created")
            print(f"    Verdict: {verdict.verdict}")
            print(f"    Top Failures: {len(verdict.top_failures)}")
            print(f"    Next Action: {verdict.next_action.type}")

            # Test 4: Verify artifacts saved and can be loaded
            print("\n[4] Verifying artifact persistence...")
            run_storage = ResearchStorage(run_id=run_id)

            loaded_memo = run_storage.load_blue_memo(result.graph_id)
            assert loaded_memo is not None
            assert loaded_memo.graph_id == result.graph_id
            print(f"  ✓ Blue Memo loaded from disk")

            loaded_verdict = run_storage.load_red_verdict(result.graph_id)
            assert loaded_verdict is not None
            assert loaded_verdict.graph_id == result.graph_id
            print(f"  ✓ Red Verdict loaded from disk")

            # Test 5: Verify artifact locations
            print("\n[5] Verifying artifact paths...")
            memo_path = Path(tmpdir) / "runs" / run_id / "blue_memos" / f"{result.graph_id}.json"
            verdict_path = Path(tmpdir) / "runs" / run_id / "red_verdicts" / f"{result.graph_id}.json"
            pack_path = Path(tmpdir) / "research_packs" / f"{pack.id}.json"

            assert memo_path.exists(), f"Blue Memo not found at {memo_path}"
            assert verdict_path.exists(), f"Red Verdict not found at {verdict_path}"
            assert pack_path.exists(), f"Research Pack not found at {pack_path}"

            print(f"  ✓ All artifacts found at expected paths:")
            print(f"    - {memo_path}")
            print(f"    - {verdict_path}")
            print(f"    - {pack_path}")

            print("\n" + "=" * 70)
            print("SMOKE TEST PASSED ✅")
            print("=" * 70)
            return 0

        finally:
            config.RESULTS_DIR = original_results


if __name__ == "__main__":
    sys.exit(main())
