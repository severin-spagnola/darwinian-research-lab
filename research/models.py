"""Data models for Research Pack + Blue Memo + Red Verdict layer.

All models are designed for determinism and JSON serialization.
"""

import hashlib
import json
from datetime import datetime
from typing import List, Dict, Any, Optional, Literal
from pydantic import BaseModel, Field


# ============================================================================
# Research Pack
# ============================================================================

class ResearchSource(BaseModel):
    """Single research source from a provider."""
    title: str
    url: str
    snippet: Optional[str] = None
    provider_rank: Optional[int] = None
    published_date: Optional[str] = None


class ResearchExtraction(BaseModel):
    """Structured extractions from research sources."""
    assumptions: List[str] = Field(default_factory=list)
    knobs: List[str] = Field(default_factory=list)
    known_failure_modes: List[str] = Field(default_factory=list)
    suggested_tests: List[str] = Field(default_factory=list)


class ResearchPack(BaseModel):
    """Run-level research pack for grounding strategy design."""
    id: str  # UUID or fingerprint-derived
    created_at: str
    query: str
    provider: Literal["youcom"] = "youcom"
    sources: List[ResearchSource] = Field(default_factory=list)
    extracted: ResearchExtraction = Field(default_factory=ResearchExtraction)
    raw: Optional[Dict[str, Any]] = None  # Provider raw response (size-bounded)
    fingerprint: str  # sha256(query + normalized response) for caching

    @staticmethod
    def compute_fingerprint(query: str, sources: List[ResearchSource]) -> str:
        """Compute deterministic fingerprint for caching."""
        normalized = {
            "query": query.strip().lower(),
            "sources": [
                {"title": s.title, "url": s.url, "snippet": s.snippet or ""}
                for s in sources
            ],
        }
        payload = json.dumps(normalized, sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()


# ============================================================================
# Blue Memo (per-child self-advocate)
# ============================================================================

class BlueMemo(BaseModel):
    """Per-child strategy self-advocacy memo (deterministic by default)."""
    run_id: str
    graph_id: str
    parent_graph_id: Optional[str] = None
    generation: Optional[int] = None
    mutation_patch_summary: List[str] = Field(default_factory=list)
    claim: str = ""
    expected_improvement: List[str] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)
    created_at: str

    @staticmethod
    def from_evaluation(
        run_id: str,
        graph_id: str,
        parent_graph_id: Optional[str],
        generation: Optional[int],
        patch_summary: List[str],
        phase3_report: Optional[Dict[str, Any]] = None,
    ) -> "BlueMemo":
        """Generate deterministic BlueMemo from evaluation artifacts.

        LLM phrasing is NOT used here - all text is template-based.
        """
        claim = _generate_claim_deterministic(patch_summary, phase3_report)
        expected_improvement = _generate_expected_improvements(phase3_report)
        risks = _generate_risks(patch_summary, phase3_report)

        return BlueMemo(
            run_id=run_id,
            graph_id=graph_id,
            parent_graph_id=parent_graph_id,
            generation=generation,
            mutation_patch_summary=patch_summary,
            claim=claim,
            expected_improvement=expected_improvement,
            risks=risks,
            created_at=datetime.now().isoformat(),
        )


def _generate_claim_deterministic(
    patch_summary: List[str], phase3_report: Optional[Dict[str, Any]]
) -> str:
    """Generate claim via templates (no LLM)."""
    if not patch_summary:
        return "Initial strategy (Adam) - no mutations applied."

    # Summarize patch ops
    ops_text = "; ".join(patch_summary[:3])  # First 3 ops
    if len(patch_summary) > 3:
        ops_text += f" (+{len(patch_summary) - 3} more)"

    return f"Applied mutations: {ops_text}"


def _generate_expected_improvements(phase3_report: Optional[Dict[str, Any]]) -> List[str]:
    """Derive expected improvements from Phase3 penalties."""
    if not phase3_report:
        return []

    p3 = phase3_report.get("phase3", {})
    improvements = []

    if p3.get("dispersion_penalty", 0) > 0:
        improvements.append("Reduce fitness dispersion across episodes")
    if p3.get("lucky_spike_penalty", 0) > 0:
        improvements.append("Eliminate lucky spike dependency")
    if p3.get("single_regime_penalty", 0) > 0:
        improvements.append("Improve regime coverage diversity")
    if p3.get("worst_case_penalty", 0) > 0:
        improvements.append("Improve worst-case episode performance")

    # Check drawdown_state issues
    episodes = p3.get("episodes", [])
    drawdown_kills = sum(
        1 for ep in episodes
        if ep.get("tags", {}).get("drawdown_state") in ["in_drawdown", "recovering"]
        and ep.get("decision") == "kill"
    )
    if drawdown_kills > len(episodes) * 0.4:
        improvements.append("Better performance during drawdown regimes")

    return improvements or ["Maintain current performance characteristics"]


def _generate_risks(
    patch_summary: List[str], phase3_report: Optional[Dict[str, Any]]
) -> List[str]:
    """Derive risks from mutation types."""
    if not patch_summary:
        return []

    risks = []

    # Check for common risky patterns
    ops_text = " ".join(patch_summary).lower()

    if "add_node" in ops_text:
        risks.append("Increased complexity may reduce robustness")
    if "remove_node" in ops_text:
        risks.append("Signal degradation from removed indicators")
    if "modify_param" in ops_text and ("period" in ops_text or "window" in ops_text):
        risks.append("Parameter sensitivity to lookback periods")
    if "rewire" in ops_text:
        risks.append("Signal flow changes may introduce regime bias")

    return risks or ["No obvious risks identified"]


# ============================================================================
# Red Verdict (global overseer)
# ============================================================================

class FailureEvidence(BaseModel):
    """Single failure with severity and evidence."""
    code: str
    severity: float  # 0.0-1.0
    evidence: str


class NextAction(BaseModel):
    """Recommended next action from Red overseer."""
    type: Literal["MUTATE", "STOP_BRANCH", "RESEARCH_TRIGGER", "NONE"]
    suggestion: str


class MetricsSummary(BaseModel):
    """Key metrics extracted from Phase3 report."""
    episodes_count: int = 0
    years_covered: List[int] = Field(default_factory=list)
    lucky_spike_triggered: bool = False
    median_return: Optional[float] = None
    dispersion: Optional[float] = None
    regime_count: int = 0


class RedVerdict(BaseModel):
    """Global overseer verdict on strategy (deterministic by default)."""
    run_id: str
    graph_id: str
    verdict: Literal["SURVIVE", "KILL"]
    top_failures: List[FailureEvidence] = Field(default_factory=list)
    strongest_evidence: List[str] = Field(default_factory=list)
    next_action: NextAction
    metrics_summary: MetricsSummary
    created_at: str

    @staticmethod
    def from_evaluation(
        run_id: str,
        graph_id: str,
        evaluation_result: "StrategyEvaluationResult",  # type: ignore
        phase3_report: Optional[Dict[str, Any]] = None,
    ) -> "RedVerdict":
        """Generate deterministic RedVerdict from evaluation.

        All scoring is deterministic - no LLM calls.
        """
        from validation.evaluation import StrategyEvaluationResult

        verdict = "SURVIVE" if evaluation_result.decision != "kill" else "KILL"

        # Compute failures deterministically
        failures = _score_failures_deterministic(evaluation_result, phase3_report)

        # Top 3 by severity
        top_failures = sorted(failures, key=lambda f: f.severity, reverse=True)[:3]

        # Extract evidence
        strongest_evidence = [f.evidence for f in top_failures]

        # Determine next action
        next_action = _determine_next_action(verdict, top_failures, phase3_report)

        # Extract metrics
        metrics = _extract_metrics_summary(phase3_report)

        return RedVerdict(
            run_id=run_id,
            graph_id=graph_id,
            verdict=verdict,
            top_failures=top_failures,
            strongest_evidence=strongest_evidence,
            next_action=next_action,
            metrics_summary=metrics,
            created_at=datetime.now().isoformat(),
        )


def _score_failures_deterministic(
    evaluation_result, phase3_report: Optional[Dict[str, Any]]
) -> List[FailureEvidence]:
    """Score all failure modes deterministically."""
    failures = []

    if not phase3_report:
        # Fallback to kill_reason
        for reason in evaluation_result.kill_reason:
            failures.append(
                FailureEvidence(
                    code=reason.upper(),
                    severity=0.8,
                    evidence=f"Kill reason: {reason}",
                )
            )
        return failures

    p3 = phase3_report.get("phase3", {})

    # Lucky spike
    if p3.get("lucky_spike_penalty", 0) > 0:
        failures.append(
            FailureEvidence(
                code="LUCKY_SPIKE",
                severity=0.9,
                evidence=f"Best episode dominates: penalty={p3['lucky_spike_penalty']:.2f}",
            )
        )

    # Years coverage
    regime_cov = p3.get("regime_coverage", {})
    years = regime_cov.get("years_covered", [])
    if len(years) < 2:
        failures.append(
            FailureEvidence(
                code="LOW_YEARS_COVERED",
                severity=0.7,
                evidence=f"Only {len(years)} year(s) covered: {years}",
            )
        )

    # Dispersion
    disp_penalty = p3.get("dispersion_penalty", 0)
    if disp_penalty > 0:
        worst = p3.get("worst_fitness", 0)
        median = p3.get("median_fitness", 0)
        failures.append(
            FailureEvidence(
                code="HIGH_DISPERSION",
                severity=min(1.0, disp_penalty / 0.5),
                evidence=f"High variance: worst={worst:.3f}, median={median:.3f}, penalty={disp_penalty:.2f}",
            )
        )

    # Drawdown underperformance
    episodes = p3.get("episodes", [])
    dd_fails = [
        ep for ep in episodes
        if ep.get("tags", {}).get("drawdown_state") in ["in_drawdown", "recovering"]
        and ep.get("fitness", 0) < 0
    ]
    if dd_fails and len(dd_fails) / max(len(episodes), 1) > 0.5:
        failures.append(
            FailureEvidence(
                code="DRAWDOWN_FAIL",
                severity=0.8,
                evidence=f"{len(dd_fails)}/{len(episodes)} drawdown/recovering episodes failed",
            )
        )

    # Single regime
    if p3.get("single_regime_penalty", 0) > 0:
        unique_regimes = regime_cov.get("unique_regimes", 0)
        failures.append(
            FailureEvidence(
                code="SINGLE_REGIME_DEPENDENT",
                severity=0.6,
                evidence=f"Only {unique_regimes} unique regime(s), penalty={p3['single_regime_penalty']:.2f}",
            )
        )

    # Negative aggregate
    if p3.get("aggregated_fitness", 0) < 0:
        failures.append(
            FailureEvidence(
                code="NEGATIVE_AGGREGATE",
                severity=1.0,
                evidence=f"Negative aggregated fitness: {p3['aggregated_fitness']:.3f}",
            )
        )

    return failures


def _determine_next_action(
    verdict: str, failures: List[FailureEvidence], phase3_report: Optional[Dict[str, Any]]
) -> NextAction:
    """Determine next action deterministically."""
    if verdict == "SURVIVE":
        return NextAction(type="MUTATE", suggestion="Strategy passed - continue evolution")

    # KILL verdict - analyze failure pattern
    if not failures:
        return NextAction(type="STOP_BRANCH", suggestion="No viable path forward")

    # Check if research might help
    research_codes = {"LUCKY_SPIKE", "SINGLE_REGIME_DEPENDENT", "DRAWDOWN_FAIL"}
    if any(f.code in research_codes for f in failures):
        top_code = failures[0].code
        return NextAction(
            type="RESEARCH_TRIGGER",
            suggestion=f"Consider targeted research on {top_code.lower().replace('_', ' ')}",
        )

    # Default: try mutation
    return NextAction(
        type="MUTATE",
        suggestion="Attempt targeted mutation to address top failure",
    )


def _extract_metrics_summary(phase3_report: Optional[Dict[str, Any]]) -> MetricsSummary:
    """Extract key metrics for frontend display."""
    if not phase3_report:
        return MetricsSummary()

    p3 = phase3_report.get("phase3", {})
    regime_cov = p3.get("regime_coverage", {})

    return MetricsSummary(
        episodes_count=len(p3.get("episodes", [])),
        years_covered=regime_cov.get("years_covered", []),
        lucky_spike_triggered=p3.get("lucky_spike_penalty", 0) > 0,
        median_return=p3.get("median_fitness"),
        dispersion=p3.get("std_fitness"),
        regime_count=regime_cov.get("unique_regimes", 0),
    )
