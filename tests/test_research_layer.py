"""Tests for Research Pack + Blue Memo + Red Verdict layer.

All tests are deterministic and do NOT hit the network.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from research.models import (
    ResearchPack,
    ResearchSource,
    ResearchExtraction,
    BlueMemo,
    RedVerdict,
    FailureEvidence,
)
from research.youcom import (
    normalize_youcom_response,
    _cache_key,
    read_cache,
    write_cache,
    search_with_cache,
    extract_insights,
    create_research_pack,
)
from research.storage import ResearchStorage
from research.service import generate_and_save_artifacts, _extract_patch_summary
from validation.evaluation import StrategyEvaluationResult
from evolution.patches import PatchSet, PatchOp


# ============================================================================
# You.com normalization and caching
# ============================================================================

class TestYouComNormalization:
    def test_normalize_youcom_response_with_hits(self):
        raw = {
            "hits": [
                {
                    "title": "Trading Strategy A",
                    "url": "https://example.com/a",
                    "snippets": ["Snippet 1", "Snippet 2"],
                    "published_date": "2024-01-01",
                },
                {
                    "title": "Trading Strategy B",
                    "url": "https://example.com/b",
                    "description": "Description B",
                },
            ]
        }

        sources = normalize_youcom_response(raw)

        assert len(sources) == 2
        assert sources[0].title == "Trading Strategy A"
        assert sources[0].url == "https://example.com/a"
        assert "Snippet 1 Snippet 2" in sources[0].snippet
        assert sources[0].provider_rank == 1

        assert sources[1].title == "Trading Strategy B"
        assert sources[1].snippet == "Description B"
        assert sources[1].provider_rank == 2

    def test_normalize_fallback_to_results(self):
        raw = {
            "results": [
                {"title": "Result 1", "link": "https://example.com/1"},
            ]
        }

        sources = normalize_youcom_response(raw)
        assert len(sources) == 1
        assert sources[0].url == "https://example.com/1"

    def test_normalize_empty_response(self):
        sources = normalize_youcom_response({})
        assert sources == []


class TestYouComCaching:
    def test_cache_key_deterministic(self):
        key1 = _cache_key("  Test Query  ", 5)
        key2 = _cache_key("test query", 5)
        assert key1 == key2  # Normalized

        key3 = _cache_key("test query", 10)
        assert key1 != key3  # Different n_results

    def test_write_and_read_cache(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            import config
            orig = config.RESULTS_DIR
            config.RESULTS_DIR = Path(tmpdir)
            try:
                sources = [
                    ResearchSource(title="Test", url="https://example.com", snippet="Snippet")
                ]

                write_cache("test query", 5, sources)
                loaded = read_cache("test query", 5)

                assert loaded is not None
                assert len(loaded) == 1
                assert loaded[0].title == "Test"
                assert loaded[0].url == "https://example.com"

            finally:
                config.RESULTS_DIR = orig

    def test_cache_miss_returns_none(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            import config
            orig = config.RESULTS_DIR
            config.RESULTS_DIR = Path(tmpdir)
            try:
                loaded = read_cache("nonexistent query", 5)
                assert loaded is None
            finally:
                config.RESULTS_DIR = orig

    def test_search_with_cache_uses_cache(self):
        """Test that search_with_cache returns cached results on second call."""
        mock_client = Mock()
        mock_client.search.return_value = {
            "hits": [
                {"title": "Result 1", "url": "https://example.com/1", "snippets": ["Snippet"]}
            ]
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            import config
            orig = config.RESULTS_DIR
            config.RESULTS_DIR = Path(tmpdir)
            try:
                # First call - cache miss
                sources1 = search_with_cache("test query", 5, client=mock_client)
                assert len(sources1) == 1
                assert mock_client.search.call_count == 1

                # Second call - cache hit
                sources2 = search_with_cache("test query", 5, client=mock_client)
                assert len(sources2) == 1
                assert mock_client.search.call_count == 1  # Not called again

                # Verify same results
                assert sources1[0].title == sources2[0].title

            finally:
                config.RESULTS_DIR = orig


# ============================================================================
# Extraction heuristics
# ============================================================================

class TestExtractionHeuristics:
    def test_extract_insights_detects_assumptions(self):
        sources = [
            ResearchSource(
                title="Mean Reversion Trading",
                url="https://example.com",
                snippet="Assumes normal distribution of returns and stationary processes",
            )
        ]

        extraction = extract_insights(sources, "mean reversion")

        assert any("statistical properties" in a.lower() for a in extraction.assumptions)

    def test_extract_insights_detects_knobs(self):
        sources = [
            ResearchSource(
                title="Moving Average Strategy",
                url="https://example.com",
                snippet="The lookback period and threshold levels are critical parameters",
            )
        ]

        extraction = extract_insights(sources, "moving average")

        assert any("period" in k.lower() or "window" in k.lower() for k in extraction.knobs)
        assert any("threshold" in k.lower() for k in extraction.knobs)

    def test_extract_insights_detects_failure_modes(self):
        sources = [
            ResearchSource(
                title="Overfitting Risks",
                url="https://example.com",
                snippet="Beware of overfitting and regime change in non-stationary markets",
            )
        ]

        extraction = extract_insights(sources, "risks")

        assert any("overfitting" in f.lower() for f in extraction.known_failure_modes)
        assert any("regime" in f.lower() for f in extraction.known_failure_modes)

    def test_extract_insights_suggests_tests(self):
        sources = [
            ResearchSource(
                title="Validation Methods",
                url="https://example.com",
                snippet="Walk forward analysis and Monte Carlo simulation are recommended",
            )
        ]

        extraction = extract_insights(sources, "validation")

        assert any("walk" in t.lower() and "forward" in t.lower() for t in extraction.suggested_tests)


# ============================================================================
# ResearchPack creation
# ============================================================================

class TestResearchPackCreation:
    def test_create_research_pack_deterministic_fingerprint(self):
        mock_client = Mock()
        mock_client.search.return_value = {
            "hits": [
                {"title": "Result 1", "url": "https://example.com/1", "snippets": ["Snippet 1"]}
            ]
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            import config
            orig = config.RESULTS_DIR
            config.RESULTS_DIR = Path(tmpdir)
            try:
                pack1 = create_research_pack("test query", n_results=5, client=mock_client)
                pack2 = create_research_pack("test query", n_results=5, client=mock_client)

                # Same fingerprint despite different timestamps
                assert pack1.fingerprint == pack2.fingerprint
                assert pack1.id == pack2.id

            finally:
                config.RESULTS_DIR = orig

    def test_create_research_pack_from_url(self):
        mock_client = Mock()
        mock_client.search.return_value = {"hits": []}

        with tempfile.TemporaryDirectory() as tmpdir:
            import config
            orig = config.RESULTS_DIR
            config.RESULTS_DIR = Path(tmpdir)
            try:
                _ = create_research_pack("https://arxiv.org/abs/1234", client=mock_client)

                # URL should be incorporated into query
                called_query = mock_client.search.call_args[0][0]
                assert "https://arxiv.org/abs/1234" in called_query

            finally:
                config.RESULTS_DIR = orig


# ============================================================================
# Storage layer
# ============================================================================

class TestResearchStorage:
    def test_save_and_load_research_pack(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            import config
            orig = config.RESULTS_DIR
            config.RESULTS_DIR = Path(tmpdir)
            try:
                storage = ResearchStorage()

                pack = ResearchPack(
                    id="test_pack_123",
                    created_at="2024-01-01T00:00:00",
                    query="test query",
                    provider="youcom",
                    sources=[],
                    extracted=ResearchExtraction(),
                    fingerprint="abc123",
                )

                storage.save_research_pack(pack)
                loaded = storage.load_research_pack("test_pack_123")

                assert loaded is not None
                assert loaded.id == "test_pack_123"
                assert loaded.query == "test query"

            finally:
                config.RESULTS_DIR = orig

    def test_save_and_load_blue_memo(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            import config
            orig = config.RESULTS_DIR
            config.RESULTS_DIR = Path(tmpdir)
            try:
                storage = ResearchStorage(run_id="test_run")

                memo = BlueMemo(
                    run_id="test_run",
                    graph_id="graph_123",
                    parent_graph_id="graph_000",
                    generation=1,
                    mutation_patch_summary=["add_node: SMA"],
                    claim="Added SMA indicator",
                    expected_improvement=["Better trend detection"],
                    risks=["Increased complexity"],
                    created_at="2024-01-01T00:00:00",
                )

                storage.save_blue_memo(memo)
                loaded = storage.load_blue_memo("graph_123")

                assert loaded is not None
                assert loaded.graph_id == "graph_123"
                assert loaded.claim == "Added SMA indicator"

            finally:
                config.RESULTS_DIR = orig

    def test_save_and_load_red_verdict(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            import config
            orig = config.RESULTS_DIR
            config.RESULTS_DIR = Path(tmpdir)
            try:
                storage = ResearchStorage(run_id="test_run")

                from research.models import NextAction, MetricsSummary

                verdict = RedVerdict(
                    run_id="test_run",
                    graph_id="graph_123",
                    verdict="KILL",
                    top_failures=[
                        FailureEvidence(code="LUCKY_SPIKE", severity=0.9, evidence="Test evidence")
                    ],
                    strongest_evidence=["Test evidence"],
                    next_action=NextAction(type="RESEARCH_TRIGGER", suggestion="Research lucky spike"),
                    metrics_summary=MetricsSummary(),
                    created_at="2024-01-01T00:00:00",
                )

                storage.save_red_verdict(verdict)
                loaded = storage.load_red_verdict("graph_123")

                assert loaded is not None
                assert loaded.verdict == "KILL"
                assert len(loaded.top_failures) == 1
                assert loaded.top_failures[0].code == "LUCKY_SPIKE"

            finally:
                config.RESULTS_DIR = orig


# ============================================================================
# BlueMemo and RedVerdict generation (deterministic)
# ============================================================================

class TestBlueMemoGeneration:
    def test_blue_memo_from_evaluation_adam(self):
        # Adam (no patch)
        memo = BlueMemo.from_evaluation(
            run_id="test_run",
            graph_id="adam",
            parent_graph_id=None,
            generation=0,
            patch_summary=[],
            phase3_report=None,
        )

        assert memo.graph_id == "adam"
        assert "Initial strategy" in memo.claim
        assert memo.parent_graph_id is None

    def test_blue_memo_from_evaluation_with_patch(self):
        patch_summary = ["add_node: RSI", "modify_param: sma_period = 20"]
        phase3_report = {
            "phase3": {
                "dispersion_penalty": 0.3,
                "lucky_spike_penalty": 0.0,
                "single_regime_penalty": 0.0,
                "worst_case_penalty": 0.0,
            }
        }

        memo = BlueMemo.from_evaluation(
            run_id="test_run",
            graph_id="child_1",
            parent_graph_id="adam",
            generation=1,
            patch_summary=patch_summary,
            phase3_report=phase3_report,
        )

        assert "RSI" in memo.claim
        assert any("dispersion" in imp.lower() for imp in memo.expected_improvement)


class TestRedVerdictGeneration:
    def test_red_verdict_survive(self):
        result = StrategyEvaluationResult(
            graph_id="graph_123",
            strategy_name="Test",
            validation_report={},
            fitness=0.5,
            decision="survive",
            kill_reason=[],
        )

        verdict = RedVerdict.from_evaluation(
            run_id="test_run",
            graph_id="graph_123",
            evaluation_result=result,
            phase3_report=None,
        )

        assert verdict.verdict == "SURVIVE"
        assert verdict.next_action.type == "MUTATE"

    def test_red_verdict_kill_with_lucky_spike(self):
        phase3_report = {
            "phase3": {
                "aggregated_fitness": -0.5,
                "median_fitness": 0.1,
                "worst_fitness": -0.3,
                "best_fitness": 0.8,
                "dispersion_penalty": 0.0,
                "lucky_spike_penalty": 0.2,
                "single_regime_penalty": 0.0,
                "worst_case_penalty": 0.0,
                "regime_coverage": {"unique_regimes": 3, "years_covered": [2020, 2021]},
                "episodes": [],
            }
        }

        result = StrategyEvaluationResult(
            graph_id="graph_123",
            strategy_name="Test",
            validation_report=phase3_report,
            fitness=-0.5,
            decision="kill",
            kill_reason=["phase3_negative_aggregate"],
        )

        verdict = RedVerdict.from_evaluation(
            run_id="test_run",
            graph_id="graph_123",
            evaluation_result=result,
            phase3_report=phase3_report,
        )

        assert verdict.verdict == "KILL"
        assert any(f.code == "LUCKY_SPIKE" for f in verdict.top_failures)
        assert verdict.next_action.type == "RESEARCH_TRIGGER"


# ============================================================================
# Service layer integration
# ============================================================================

class TestServiceLayer:
    def test_extract_patch_summary(self):
        patch = PatchSet(
            patch_id="patch_1",
            parent_graph_id="adam",
            description="Test patch",
            ops=[
                PatchOp(op_type="add_node", new_node={"type": "RSI"}),
                PatchOp(op_type="modify_param", node_id="sma", param_name="period", param_value=20),
            ],
        )

        summary = _extract_patch_summary(patch)

        assert len(summary) == 2
        assert "add_node: RSI" in summary
        assert "modify_param: sma.period = 20" in summary

    def test_generate_and_save_artifacts(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            import config
            orig = config.RESULTS_DIR
            config.RESULTS_DIR = Path(tmpdir)
            try:
                result = StrategyEvaluationResult(
                    graph_id="graph_123",
                    strategy_name="Test",
                    validation_report={
                        "phase3": {
                            "aggregated_fitness": 0.5,
                            "median_fitness": 0.4,
                            "worst_fitness": 0.3,
                            "best_fitness": 0.6,
                            "dispersion_penalty": 0.0,
                            "lucky_spike_penalty": 0.0,
                            "single_regime_penalty": 0.0,
                            "worst_case_penalty": 0.0,
                            "regime_coverage": {"unique_regimes": 2, "years_covered": [2020]},
                            "episodes": [],
                        }
                    },
                    fitness=0.5,
                    decision="survive",
                    kill_reason=[],
                )

                memo, verdict = generate_and_save_artifacts(
                    run_id="test_run",
                    evaluation_result=result,
                    parent_graph_id=None,
                    generation=0,
                    patch=None,
                )

                assert memo.graph_id == "graph_123"
                assert verdict.graph_id == "graph_123"
                assert verdict.verdict == "SURVIVE"

                # Verify files saved
                storage = ResearchStorage(run_id="test_run")
                loaded_memo = storage.load_blue_memo("graph_123")
                loaded_verdict = storage.load_red_verdict("graph_123")

                assert loaded_memo is not None
                assert loaded_verdict is not None

            finally:
                config.RESULTS_DIR = orig


# ============================================================================
# Determinism tests
# ============================================================================

class TestDeterminism:
    def test_fingerprint_stable(self):
        sources = [
            ResearchSource(title="A", url="https://example.com/a", snippet="snippet a"),
            ResearchSource(title="B", url="https://example.com/b", snippet="snippet b"),
        ]

        fp1 = ResearchPack.compute_fingerprint("test query", sources)
        fp2 = ResearchPack.compute_fingerprint("test query", sources)

        assert fp1 == fp2

        # Different order should still match (normalized)
        fp3 = ResearchPack.compute_fingerprint("Test Query", sources)  # Different case
        assert fp1 == fp3

    def test_verdict_scoring_deterministic(self):
        phase3_report = {
            "phase3": {
                "aggregated_fitness": -0.2,
                "median_fitness": 0.1,
                "worst_fitness": -0.3,
                "dispersion_penalty": 0.3,
                "lucky_spike_penalty": 0.0,
                "single_regime_penalty": 0.0,
                "worst_case_penalty": 0.0,
                "regime_coverage": {"unique_regimes": 2, "years_covered": [2020]},
                "episodes": [],
            }
        }

        result = StrategyEvaluationResult(
            graph_id="graph_123",
            strategy_name="Test",
            validation_report=phase3_report,
            fitness=-0.2,
            decision="kill",
            kill_reason=["phase3_negative_aggregate"],
        )

        verdict1 = RedVerdict.from_evaluation("run1", "graph_123", result, phase3_report)
        verdict2 = RedVerdict.from_evaluation("run1", "graph_123", result, phase3_report)

        # Same failures, same order, same severity
        assert len(verdict1.top_failures) == len(verdict2.top_failures)
        for f1, f2 in zip(verdict1.top_failures, verdict2.top_failures):
            assert f1.code == f2.code
            assert f1.severity == f2.severity
