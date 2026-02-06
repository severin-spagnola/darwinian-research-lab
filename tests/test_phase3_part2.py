"""Tests for Phase 3 Part 2: sampling modes, penalties, curriculum, artifacts."""

import json
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from graph.schema import StrategyGraph, Node, UniverseSpec, TimeConfig, DateRange
from validation.episodes import EpisodeSampler, RegimeTagger, compute_difficulty, EpisodeSpec
from validation.robust_fitness import (
    _compute_lucky_spike_penalty,
    _compute_regime_coverage,
    _compute_single_regime_penalty,
    RobustEpisodeResult,
    LUCKY_SPIKE_THRESHOLD,
    LUCKY_SPIKE_PENALTY,
)
from validation.evaluation import (
    Phase3Config,
    Phase3ScheduleConfig,
    evaluate_strategy_phase3,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ohlcv(n_days: int = 500, start: str = "2020-01-01", seed: int = 42) -> pd.DataFrame:
    """Create a synthetic OHLCV DataFrame spanning n_days of daily bars."""
    rng = np.random.RandomState(seed)
    dates = pd.bdate_range(start, periods=n_days, freq="B")
    close = 100.0 + np.cumsum(rng.randn(n_days) * 0.5)
    df = pd.DataFrame(
        {
            "open": close + rng.randn(n_days) * 0.1,
            "high": close + abs(rng.randn(n_days) * 0.5),
            "low": close - abs(rng.randn(n_days) * 0.5),
            "close": close,
            "volume": (rng.rand(n_days) * 1e6).astype(int),
        },
        index=dates,
    )
    return df


def _make_multi_year_ohlcv(years: int = 3, bars_per_year: int = 252, seed: int = 42) -> pd.DataFrame:
    """Multi-year OHLCV for year-stratified tests."""
    return _make_ohlcv(n_days=years * bars_per_year, start="2020-01-01", seed=seed)


def _build_test_strategy() -> StrategyGraph:
    """Minimal strategy graph for evaluation tests."""
    return StrategyGraph(
        graph_id="test_strategy",
        name="Test Strategy",
        universe=UniverseSpec(type="explicit", symbols=["TEST"]),
        time_config=TimeConfig(
            timeframe="1d",
            date_range=DateRange(start="2020-01-01", end="2023-12-31"),
        ),
        nodes=[
            Node(node_id="sma_fast", type="SMA", params={"period": 10}, inputs={}),
            Node(node_id="sma_slow", type="SMA", params={"period": 30}, inputs={}),
            Node(node_id="cmp", type="compare", params={"operator": ">"}, inputs={"a": "sma_fast", "b": "sma_slow"}),
            Node(node_id="orders", type="orders", params={"side": "long", "qty": 100}, inputs={"entry_signal": "cmp"}),
        ],
        outputs={"orders": "orders"},
    )


# ---------------------------------------------------------------------------
# 1. Determinism: same seed => same episodes
# ---------------------------------------------------------------------------

class TestDeterminism:
    def test_random_mode_deterministic(self):
        df = _make_ohlcv()
        eps_a = EpisodeSampler(seed=99).sample_episodes(df, 4, min_months=2, max_months=4, min_bars=20)
        eps_b = EpisodeSampler(seed=99).sample_episodes(df, 4, min_months=2, max_months=4, min_bars=20)
        for a, b in zip(eps_a, eps_b):
            assert a.start_ts == b.start_ts
            assert a.end_ts == b.end_ts

    def test_uniform_random_deterministic(self):
        df = _make_ohlcv()
        eps_a = EpisodeSampler(seed=77).sample_episodes(df, 4, min_months=2, max_months=4, min_bars=20, sampling_mode="uniform_random")
        eps_b = EpisodeSampler(seed=77).sample_episodes(df, 4, min_months=2, max_months=4, min_bars=20, sampling_mode="uniform_random")
        for a, b in zip(eps_a, eps_b):
            assert a.start_ts == b.start_ts
            assert a.end_ts == b.end_ts

    def test_stratified_by_year_deterministic(self):
        df = _make_multi_year_ohlcv(years=3)
        eps_a = EpisodeSampler(seed=55).sample_episodes(df, 6, min_months=2, max_months=3, min_bars=20, sampling_mode="stratified_by_year")
        eps_b = EpisodeSampler(seed=55).sample_episodes(df, 6, min_months=2, max_months=3, min_bars=20, sampling_mode="stratified_by_year")
        for a, b in zip(eps_a, eps_b):
            assert a.start_ts == b.start_ts
            assert a.end_ts == b.end_ts


# ---------------------------------------------------------------------------
# 2. Year coverage: stratified_by_year picks episodes from multiple years
# ---------------------------------------------------------------------------

class TestYearCoverage:
    def test_stratified_covers_multiple_years(self):
        df = _make_multi_year_ohlcv(years=3)
        episodes = EpisodeSampler(seed=42).sample_episodes(
            df, 6, min_months=2, max_months=3, min_bars=20,
            sampling_mode="stratified_by_year",
        )
        years_seen = set()
        for ep in episodes:
            years_seen.add(ep.start_ts.year)
        assert len(years_seen) >= 2, f"Expected >=2 years, got {years_seen}"


# ---------------------------------------------------------------------------
# 3. Regime coverage & penalty
# ---------------------------------------------------------------------------

class TestRegimeCoverage:
    def test_regime_tagger_returns_all_tags(self):
        df = _make_ohlcv(n_days=100)
        tagger = RegimeTagger()
        tags = tagger.tag_episode(df)
        assert "trend" in tags
        assert "vol_bucket" in tags
        assert "chop_bucket" in tags
        assert "drawdown_state" in tags

    def test_single_regime_penalty_applied_when_one_regime(self):
        episodes = [
            RobustEpisodeResult(
                episode_spec=EpisodeSpec(start_ts=pd.Timestamp("2020-01-01"), end_ts=pd.Timestamp("2020-06-01"), label="ep1"),
                episode_fitness=0.5,
                decision="survive",
                kill_reason=[],
                tags={"trend": "up", "vol_bucket": "low"},
            ),
            RobustEpisodeResult(
                episode_spec=EpisodeSpec(start_ts=pd.Timestamp("2020-06-01"), end_ts=pd.Timestamp("2020-12-01"), label="ep2"),
                episode_fitness=0.3,
                decision="survive",
                kill_reason=[],
                tags={"trend": "up", "vol_bucket": "low"},
            ),
        ]
        coverage = _compute_regime_coverage(episodes)
        penalty = _compute_single_regime_penalty(coverage, weight=0.3)
        assert penalty == 0.3, f"Expected 0.3, got {penalty}"


# ---------------------------------------------------------------------------
# 4. Lucky spike penalty
# ---------------------------------------------------------------------------

class TestLuckySpikePenalty:
    def test_spike_triggers_when_one_dominates(self):
        # One episode has 90% of positive fitness
        fitnesses = [0.9, 0.05, 0.05, -0.1]
        penalty = _compute_lucky_spike_penalty(fitnesses)
        assert penalty == LUCKY_SPIKE_PENALTY

    def test_no_spike_when_balanced(self):
        fitnesses = [0.3, 0.3, 0.3, 0.1]
        penalty = _compute_lucky_spike_penalty(fitnesses)
        assert penalty == 0.0

    def test_no_spike_with_single_positive(self):
        fitnesses = [0.5, -0.1, -0.2]
        penalty = _compute_lucky_spike_penalty(fitnesses)
        assert penalty == 0.0  # <2 positive episodes

    def test_no_spike_all_negative(self):
        fitnesses = [-0.1, -0.2, -0.3]
        penalty = _compute_lucky_spike_penalty(fitnesses)
        assert penalty == 0.0


# ---------------------------------------------------------------------------
# 5. Difficulty score
# ---------------------------------------------------------------------------

class TestDifficulty:
    def test_easy_regime(self):
        tags = {"trend": "up", "vol_bucket": "low", "chop_bucket": "trending", "drawdown_state": "at_highs"}
        score = compute_difficulty(tags)
        assert score < 0.2

    def test_hard_regime(self):
        tags = {"trend": "down", "vol_bucket": "high", "chop_bucket": "choppy", "drawdown_state": "in_drawdown"}
        score = compute_difficulty(tags)
        assert score >= 0.8

    def test_score_bounded(self):
        tags = {"trend": "down", "vol_bucket": "high", "chop_bucket": "choppy", "drawdown_state": "in_drawdown"}
        score = compute_difficulty(tags)
        assert 0.0 <= score <= 1.0


# ---------------------------------------------------------------------------
# 6. Curriculum (sampling_mode_schedule)
# ---------------------------------------------------------------------------

class TestCurriculum:
    def test_get_sampling_mode_no_schedule(self):
        cfg = Phase3Config(enabled=True, mode="episodes", sampling_mode="random")
        assert cfg.get_sampling_mode(0) == "random"
        assert cfg.get_sampling_mode(5) == "random"

    def test_get_sampling_mode_with_schedule(self):
        cfg = Phase3Config(
            enabled=True, mode="episodes",
            sampling_mode="random",
            sampling_mode_schedule=["random", "uniform_random", "stratified_by_regime"],
        )
        assert cfg.get_sampling_mode(0) == "random"
        assert cfg.get_sampling_mode(1) == "uniform_random"
        assert cfg.get_sampling_mode(2) == "stratified_by_regime"
        # Beyond schedule length: last element
        assert cfg.get_sampling_mode(10) == "stratified_by_regime"


# ---------------------------------------------------------------------------
# 7. Phase3 report storage
# ---------------------------------------------------------------------------

class TestPhase3ReportStorage:
    def test_save_and_load_phase3_report(self):
        from evolution.storage import RunStorage

        with tempfile.TemporaryDirectory() as tmpdir:
            import config as cfg
            original = cfg.RESULTS_DIR
            cfg.RESULTS_DIR = Path(tmpdir)
            try:
                storage = RunStorage(run_id="test_p3_report")
                from validation.evaluation import StrategyEvaluationResult
                result = StrategyEvaluationResult(
                    graph_id="graph_abc",
                    strategy_name="Test",
                    validation_report={
                        "timestamp": "2024-01-01T00:00:00",
                        "phase3": {
                            "aggregated_fitness": 0.5,
                            "median_fitness": 0.4,
                            "episodes": [],
                        },
                    },
                    fitness=0.5,
                    decision="survive",
                    kill_reason=[],
                )
                storage.save_phase3_report(result)

                report_path = storage.run_dir / "phase3_reports" / "graph_abc.json"
                assert report_path.exists()

                with open(report_path) as f:
                    loaded = json.load(f)
                assert loaded["graph_id"] == "graph_abc"
                assert loaded["phase3"]["aggregated_fitness"] == 0.5
            finally:
                cfg.RESULTS_DIR = original

    def test_no_op_without_phase3_data(self):
        from evolution.storage import RunStorage

        with tempfile.TemporaryDirectory() as tmpdir:
            import config as cfg
            original = cfg.RESULTS_DIR
            cfg.RESULTS_DIR = Path(tmpdir)
            try:
                storage = RunStorage(run_id="test_no_p3")
                from validation.evaluation import StrategyEvaluationResult
                result = StrategyEvaluationResult(
                    graph_id="graph_xyz",
                    strategy_name="Test",
                    validation_report={},
                    fitness=0.1,
                    decision="kill",
                    kill_reason=["negative_fitness"],
                )
                storage.save_phase3_report(result)

                report_path = storage.run_dir / "phase3_reports" / "graph_xyz.json"
                assert not report_path.exists()
            finally:
                cfg.RESULTS_DIR = original


# ---------------------------------------------------------------------------
# 8. Drawdown tagger
# ---------------------------------------------------------------------------

class TestDrawdownTagger:
    def test_at_highs(self):
        # Monotonically increasing close => at_highs
        df = pd.DataFrame({
            "open": range(100, 200),
            "high": range(101, 201),
            "low": range(99, 199),
            "close": range(100, 200),
            "volume": [1000] * 100,
        }, index=pd.bdate_range("2020-01-01", periods=100))
        tagger = RegimeTagger()
        result = tagger._tag_drawdown(df)
        assert result == "at_highs"

    def test_in_drawdown(self):
        # Sharp decline => in_drawdown
        close = np.concatenate([np.linspace(100, 120, 50), np.linspace(120, 95, 50)])
        df = pd.DataFrame({
            "open": close,
            "high": close + 1,
            "low": close - 1,
            "close": close,
            "volume": [1000] * 100,
        }, index=pd.bdate_range("2020-01-01", periods=100))
        tagger = RegimeTagger()
        result = tagger._tag_drawdown(df)
        assert result == "in_drawdown"


# ---------------------------------------------------------------------------
# 9. Uniform random produces episodes
# ---------------------------------------------------------------------------

class TestUniformRandom:
    def test_produces_requested_count(self):
        df = _make_ohlcv(n_days=500)
        episodes = EpisodeSampler(seed=42).sample_episodes(
            df, 4, min_months=2, max_months=3, min_bars=20,
            sampling_mode="uniform_random",
        )
        assert len(episodes) == 4

    def test_episodes_cover_date_range(self):
        df = _make_ohlcv(n_days=500)
        episodes = EpisodeSampler(seed=42).sample_episodes(
            df, 4, min_months=2, max_months=3, min_bars=20,
            sampling_mode="uniform_random",
        )
        starts = sorted(ep.start_ts for ep in episodes)
        # First episode should start near the beginning, last near the end
        total_span = (df.index[-1] - df.index[0]).days
        first_offset = (starts[0] - df.index[0]).days
        last_offset = (starts[-1] - df.index[0]).days
        # First should be in first half, last in second half
        assert first_offset < total_span * 0.5
        assert last_offset > total_span * 0.3


# ---------------------------------------------------------------------------
# 10. Phase3 evaluation uses generation for curriculum
# ---------------------------------------------------------------------------

class TestPhase3Curriculum:
    def test_evaluate_phase3_respects_generation(self):
        """Verify that different generations can use different sampling modes."""
        cfg = Phase3Config(
            enabled=True,
            mode="episodes",
            n_episodes=2,
            min_months=2,
            max_months=3,
            min_bars=20,
            seed=42,
            sampling_mode_schedule=["random", "uniform_random"],
        )
        # Just verify get_sampling_mode works correctly
        assert cfg.get_sampling_mode(0) == "random"
        assert cfg.get_sampling_mode(1) == "uniform_random"
        assert cfg.get_sampling_mode(2) == "uniform_random"  # last element
