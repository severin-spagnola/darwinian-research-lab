"""Strategy evaluation and survival gate.

Canonical interface for evaluating strategies with deterministic kill/survive decisions.
"""

import pandas as pd
from typing import Dict, Any, List, Literal, Optional
from dataclasses import dataclass, asdict

from graph.schema import StrategyGraph
from validation.overfit_tests import run_full_validation
from validation.fitness import score_validation
from validation.reporting import ValidationReport, create_validation_report
from validation.robust_fitness import (
    evaluate_strategy_on_episodes,
    RobustAggregateResult,
)


# ===== FAILURE LABELS SEMANTICS =====
# These are the canonical failure labels that can trigger kill decisions.
# Labels are generated automatically by ValidationReport.get_failure_labels()
#
# CRITICAL FAILURES (auto-kill):
#   - holdout_sign_flip: Strategy returns positive on train, negative on holdout
#   - severe_holdout_degradation: Holdout return < 30% of train return
#   - no_holdout_trades: No trades executed in holdout period
#   - too_few_holdout_trades: Holdout trades < 10 (Phase 6.5 robustness)
#   - too_few_holdout_days: Trades on < 3 unique days (Phase 6.5 robustness)
#   - negative_fitness: Final fitness score < 0
#
# WARNING FAILURES (may kill depending on severity):
#   - concentrated_returns: Concentration penalty > 0.5 (one window dominates)
#   - performance_cliff: Cliff penalty > 0.5 (second half worse than first)
#   - parameter_fragile: Sign flip penalty > 0.2 (parameter sensitive)
#   - high_fragility: Fragility score > 0.5 (high parameter dispersion)
#
# These labels are frozen and documented to ensure deterministic behavior
# across evolution generations.
# ===================================


DecisionType = Literal["kill", "survive", "mutate_only"]


@dataclass
class StrategyEvaluationResult:
    """Canonical result of strategy evaluation.

    This is the single source of truth for strategy fitness and survival decisions.
    Used throughout the evolution pipeline.
    """

    graph_id: str
    strategy_name: str
    validation_report: Dict[str, Any]  # ValidationReport.to_dict()
    fitness: float
    decision: DecisionType
    kill_reason: List[str]  # Empty if decision != "kill"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    def is_survivor(self) -> bool:
        """Check if strategy survived evaluation."""
        return self.decision == "survive"

    def can_mutate(self) -> bool:
        """Check if strategy can be used for mutations."""
        return self.decision in ["survive", "mutate_only"]


@dataclass
class Phase3ScheduleConfig:
    """Controls time-dependent evolutionary pressure across generations.

    Allows early generations (grace period) to explore without being killed,
    then ramps harshness over subsequent generations.
    """

    grace_generations: int = 1
    """Number of initial generations where KILL is suppressed (decision becomes mutate_only)."""

    kill_gate_start_gen: int = 1
    """Generation index (0-based) at which strict kill gate activates.
    Strategies evaluated before this generation are never hard-killed."""

    min_holdout_trades_schedule: Optional[List[int]] = None
    """Per-generation minimum holdout trades. Index = generation.
    Falls back to default (3) for generations beyond the list length.
    Example: [0, 3, 10] means gen0=0, gen1=3, gen2+=10."""

    penalty_weight_schedule: Optional[List[float]] = None
    """Per-generation penalty multiplier (scales worst-case + dispersion + regime penalties).
    Example: [0.0, 0.5, 1.0] means no penalties gen0, half gen1, full gen2+."""

    holdout_weight_schedule: Optional[List[float]] = None
    """Per-generation holdout weight (influences how much holdout performance matters).
    Example: [0.6, 0.7, 0.8] ramps importance over generations."""

    mutate_on_kill_during_grace: bool = True
    """If True, killed strategies during grace period get decision=mutate_only
    instead of kill, so lineage continues."""

    def get_min_holdout_trades(self, generation: int) -> int:
        """Get minimum holdout trades for a given generation."""
        if not self.min_holdout_trades_schedule:
            return 3  # default
        if generation < len(self.min_holdout_trades_schedule):
            return self.min_holdout_trades_schedule[generation]
        return self.min_holdout_trades_schedule[-1]

    def get_penalty_weight(self, generation: int) -> float:
        """Get penalty multiplier for a given generation."""
        if not self.penalty_weight_schedule:
            return 1.0  # default: full penalties
        if generation < len(self.penalty_weight_schedule):
            return self.penalty_weight_schedule[generation]
        return self.penalty_weight_schedule[-1]

    def get_holdout_weight(self, generation: int) -> float:
        """Get holdout weight for a given generation."""
        if not self.holdout_weight_schedule:
            return 0.8  # default
        if generation < len(self.holdout_weight_schedule):
            return self.holdout_weight_schedule[generation]
        return self.holdout_weight_schedule[-1]

    def is_grace_period(self, generation: int) -> bool:
        """Check if a generation is within the grace period."""
        return generation < self.grace_generations

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for run_config.json."""
        return {
            "grace_generations": self.grace_generations,
            "kill_gate_start_gen": self.kill_gate_start_gen,
            "min_holdout_trades_schedule": self.min_holdout_trades_schedule,
            "penalty_weight_schedule": self.penalty_weight_schedule,
            "holdout_weight_schedule": self.holdout_weight_schedule,
            "mutate_on_kill_during_grace": self.mutate_on_kill_during_grace,
        }


@dataclass
class Phase3Config:
    enabled: bool = False
    mode: str = "baseline"  # "episodes" to enable Phase 3 sampling
    n_episodes: int = 8
    min_months: int = 6
    max_months: int = 12
    min_bars: int = 120
    seed: Optional[int] = None
    sampling_mode: str = "random"  # "random", "uniform_random", "stratified_by_regime", "stratified_by_year"
    min_trades_per_episode: int = 3  # Minimum trades for valid episode
    regime_penalty_weight: float = 0.3  # Weight for single-regime dependence penalty
    abort_on_all_episode_failures: bool = True  # Raise error if all episodes fail (dev safety)
    schedule: Optional[Phase3ScheduleConfig] = None  # Adaptive pressure schedule
    sampling_mode_schedule: Optional[List[str]] = None
    """Per-generation sampling mode override.
    Example: ["random", "uniform_random", "stratified_by_regime"] means
    gen0=random, gen1=uniform_random, gen2+=stratified_by_regime.
    Falls back to ``sampling_mode`` for generations beyond the list."""

    # Research layer config (additive - no breaking changes)
    research_pack_id: Optional[str] = None
    """Optional research pack ID to reference for this run."""
    research_budget_per_generation: int = 0
    """Number of triggered research queries allowed per generation (default 0 = disabled)."""
    research_on_kill_reasons: Optional[List[str]] = None
    """Kill reasons that trigger research (e.g. ['LUCKY_SPIKE', 'DRAWDOWN_FAIL'])."""
    generate_memos_verdicts: bool = True
    """Generate Blue Memos and Red Verdicts for all evaluations (default True)."""

    def __post_init__(self):
        if self.research_on_kill_reasons is None:
            self.research_on_kill_reasons = []

    def get_sampling_mode(self, generation: int = 0) -> str:
        """Return sampling mode for a given generation (curriculum support)."""
        if not self.sampling_mode_schedule:
            return self.sampling_mode
        if generation < len(self.sampling_mode_schedule):
            return self.sampling_mode_schedule[generation]
        return self.sampling_mode_schedule[-1]


def evaluate_strategy(
    strategy: StrategyGraph,
    data: pd.DataFrame,
    train_frac: float = 0.75,
    k_windows: int = 6,
    n_jitter: int = 10,
    jitter_pct: float = 0.1,
    initial_capital: float = 100000.0,
) -> StrategyEvaluationResult:
    """Evaluate a strategy and determine survival.

    Runs complete validation suite and applies deterministic kill/survive rules.

    Args:
        strategy: StrategyGraph to evaluate
        data: OHLCV DataFrame for backtesting
        train_frac: Train/holdout split fraction
        k_windows: Number of subwindows for stability test
        n_jitter: Number of parameter jitter runs
        jitter_pct: Parameter jitter percentage
        initial_capital: Starting capital

    Returns:
        StrategyEvaluationResult with decision and reasons

    Raises:
        Exception: If validation fails catastrophically
    """
    # Run full validation suite
    validation_results = run_full_validation(
        strategy=strategy,
        data=data,
        train_frac=train_frac,
        k_windows=k_windows,
        n_jitter=n_jitter,
        jitter_pct=jitter_pct,
        initial_capital=initial_capital,
    )

    # Calculate fitness
    fitness_results = score_validation(validation_results)

    # Create validation report
    report = create_validation_report(
        strategy_id=strategy.graph_id,
        strategy_name=strategy.name,
        validation_results=validation_results,
        fitness_results=fitness_results,
    )

    # Get failure labels
    failure_labels = report.get_failure_labels()
    fitness = fitness_results['fitness']

    # Apply deterministic survival rules
    decision, kill_reason = _apply_survival_gate(failure_labels, fitness)

    return StrategyEvaluationResult(
        graph_id=strategy.graph_id,
        strategy_name=strategy.name,
        validation_report=report.to_dict(),
        fitness=fitness,
        decision=decision,
        kill_reason=kill_reason,
    )


def _apply_survival_gate(
    failure_labels: List[str], fitness: float
) -> tuple[DecisionType, List[str]]:
    """Apply deterministic survival rules.

    Args:
        failure_labels: List of failure labels from validation
        fitness: Final fitness score

    Returns:
        (decision, kill_reasons)

    Rules (in order of priority):
        1. fitness < 0 → KILL
        2. no_holdout_trades → KILL
        3. too_few_holdout_trades → KILL (Phase 6.5)
        4. too_few_holdout_days → KILL (Phase 6.5)
        5. severe_holdout_degradation → KILL
        6. holdout_sign_flip → KILL
        7. else → SURVIVE
    """
    kill_reasons = []

    # Rule 1: Negative fitness
    if fitness < 0:
        kill_reasons.append("negative_fitness")

    # Rule 2: No trades in holdout
    if "no_holdout_trades" in failure_labels:
        kill_reasons.append("no_holdout_trades")

    # Rule 3: Too few holdout trades (Phase 6.5)
    if "too_few_holdout_trades" in failure_labels:
        kill_reasons.append("too_few_holdout_trades")

    # Rule 4: Too few holdout days (Phase 6.5)
    if "too_few_holdout_days" in failure_labels:
        kill_reasons.append("too_few_holdout_days")

    # Rule 5: Severe degradation
    if "severe_holdout_degradation" in failure_labels:
        kill_reasons.append("severe_holdout_degradation")

    # Rule 6: Sign flip
    if "holdout_sign_flip" in failure_labels:
        kill_reasons.append("holdout_sign_flip")

    # Decision
    if kill_reasons:
        return "kill", kill_reasons
    else:
        return "survive", []


def evaluate_many(
    strategies: List[StrategyGraph],
    data: pd.DataFrame,
    train_frac: float = 0.75,
    k_windows: int = 6,
    n_jitter: int = 10,
    jitter_pct: float = 0.1,
    initial_capital: float = 100000.0,
    verbose: bool = True,
) -> List[StrategyEvaluationResult]:
    """Evaluate multiple strategies in batch.

    Args:
        strategies: List of StrategyGraphs to evaluate
        data: OHLCV DataFrame for backtesting
        train_frac: Train/holdout split fraction
        k_windows: Number of subwindows for stability test
        n_jitter: Number of parameter jitter runs
        jitter_pct: Parameter jitter percentage
        initial_capital: Starting capital
        verbose: Print progress

    Returns:
        List of StrategyEvaluationResults (one per strategy)
    """
    results = []

    for i, strategy in enumerate(strategies):
        if verbose:
            print(f"Evaluating {i+1}/{len(strategies)}: {strategy.name}...", end=" ")

        try:
            result = evaluate_strategy(
                strategy=strategy,
                data=data,
                train_frac=train_frac,
                k_windows=k_windows,
                n_jitter=n_jitter,
                jitter_pct=jitter_pct,
                initial_capital=initial_capital,
            )
            results.append(result)

            if verbose:
                print(f"{result.decision.upper()} (fitness={result.fitness:.3f})")

        except Exception as e:
            # Strategy failed catastrophically (e.g., execution error)
            if verbose:
                print(f"KILL (error: {e})")

            # Create kill result
            result = StrategyEvaluationResult(
                graph_id=strategy.graph_id,
                strategy_name=strategy.name,
                validation_report={},
                fitness=-999.0,  # Sentinel value for catastrophic failure
                decision="kill",
                kill_reason=["catastrophic_failure", str(e)],
            )
            results.append(result)

    return results


def evaluate_strategy_phase3(
    strategy: StrategyGraph,
    data: pd.DataFrame,
    initial_capital: float = 100000.0,
    phase3_config: Optional[Phase3Config] = None,
    generation: int = 0,
) -> StrategyEvaluationResult:
    """Phase 3 evaluation for episode-based robustness.

    Args:
        generation: Current generation index (used for curriculum sampling).
    """
    if not phase3_config or not phase3_config.enabled or phase3_config.mode != "episodes":
        return evaluate_strategy(strategy, data, initial_capital=initial_capital)

    # Resolve sampling mode for this generation (curriculum support)
    effective_sampling_mode = phase3_config.get_sampling_mode(generation)

    aggregate = evaluate_strategy_on_episodes(
        strategy=strategy,
        data=data,
        n_episodes=phase3_config.n_episodes,
        min_months=phase3_config.min_months,
        max_months=phase3_config.max_months,
        min_bars=phase3_config.min_bars,
        seed=phase3_config.seed,
        initial_capital=initial_capital,
        sampling_mode=effective_sampling_mode,
        min_trades_per_episode=phase3_config.min_trades_per_episode,
        regime_penalty_weight=phase3_config.regime_penalty_weight,
        abort_on_all_failures=phase3_config.abort_on_all_episode_failures,
    )

    failure_labels: List[str] = []
    if aggregate.aggregated_fitness < 0:
        failure_labels.append("phase3_negative_aggregate")
    if aggregate.worst_fitness < aggregate.median_fitness - 0.3:
        failure_labels.append("phase3_dispersion")

    decision = "kill" if failure_labels else "survive"
    kill_reason = failure_labels

    # Build explanation object
    explanation = _build_phase3_explanation(
        decision, failure_labels, aggregate
    )

    report = {
        "strategy_id": strategy.graph_id,
        "strategy_name": strategy.name,
        "timestamp": pd.Timestamp.now().isoformat(),
        "phase3": {
            "aggregated_fitness": round(aggregate.aggregated_fitness, 3),
            "median_fitness": round(aggregate.median_fitness, 3),
            "worst_fitness": round(aggregate.worst_fitness, 3),
            "best_fitness": round(aggregate.best_fitness, 3),
            "std_fitness": round(aggregate.std_fitness, 3),
            "worst_case_penalty": aggregate.worst_case_penalty,
            "dispersion_penalty": aggregate.dispersion_penalty,
            "single_regime_penalty": aggregate.single_regime_penalty,
            "lucky_spike_penalty": aggregate.lucky_spike_penalty,
            "regime_coverage": aggregate.regime_coverage,
            "n_trades_per_episode": aggregate.n_trades_per_episode,
            "explanation": explanation,
            "episodes": [
                {
                    "label": ep.episode_spec.label,
                    "start_ts": ep.episode_spec.start_ts.isoformat(),
                    "end_ts": ep.episode_spec.end_ts.isoformat(),
                    "fitness": round(ep.episode_fitness, 3),
                    "decision": ep.decision,
                    "kill_reason": ep.kill_reason,
                    "tags": ep.tags,
                    "difficulty": ep.episode_spec.difficulty,
                    "error_details": ep.error_details,
                    "debug_stats": ep.debug_stats,
                }
                for ep in aggregate.episodes
            ],
        },
    }

    return StrategyEvaluationResult(
        graph_id=strategy.graph_id,
        strategy_name=strategy.name,
        validation_report=report,
        fitness=aggregate.aggregated_fitness,
        decision=decision,
        kill_reason=kill_reason,
    )


def _build_phase3_explanation(
    decision: str,
    failure_labels: List[str],
    aggregate: RobustAggregateResult,
) -> Dict[str, Any]:
    """Build a 'why survived / why killed' explanation object.

    Purely derived from metrics and labels — no LLM involved.
    """
    reasons: List[str] = []
    penalties_applied: List[str] = []

    if aggregate.worst_case_penalty > 0:
        penalties_applied.append(
            f"worst_case={aggregate.worst_case_penalty:.2f} (episode fitness < -0.5)"
        )
    if aggregate.dispersion_penalty > 0:
        penalties_applied.append(
            f"dispersion={aggregate.dispersion_penalty:.2f} (std > 0.3)"
        )
    if aggregate.single_regime_penalty > 0:
        penalties_applied.append(
            f"single_regime={aggregate.single_regime_penalty:.2f} (regime-dependent)"
        )
    if aggregate.lucky_spike_penalty > 0:
        penalties_applied.append(
            f"lucky_spike={aggregate.lucky_spike_penalty:.2f} (best ep dominates)"
        )

    if decision == "kill":
        if "phase3_negative_aggregate" in failure_labels:
            reasons.append(
                f"Aggregated fitness ({aggregate.aggregated_fitness:.3f}) is negative"
            )
        if "phase3_dispersion" in failure_labels:
            reasons.append(
                f"High dispersion: worst ({aggregate.worst_fitness:.3f}) far below "
                f"median ({aggregate.median_fitness:.3f})"
            )
    else:
        reasons.append(
            f"Positive aggregated fitness ({aggregate.aggregated_fitness:.3f}) "
            f"with acceptable dispersion"
        )

    n_episodes = len(aggregate.episodes)
    n_failed = sum(1 for e in aggregate.episodes if e.error_details is not None)

    return {
        "decision": decision,
        "reasons": reasons,
        "penalties_applied": penalties_applied,
        "total_penalty": round(
            aggregate.worst_case_penalty
            + aggregate.dispersion_penalty
            + aggregate.single_regime_penalty
            + aggregate.lucky_spike_penalty,
            3,
        ),
        "episodes_evaluated": n_episodes,
        "episodes_failed": n_failed,
        "regimes_covered": aggregate.regime_coverage.get("unique_regimes", 0),
        "years_covered": aggregate.regime_coverage.get("years_covered", []),
    }


def apply_schedule_override(
    result: StrategyEvaluationResult,
    schedule: Phase3ScheduleConfig,
    generation: int,
) -> StrategyEvaluationResult:
    """Apply generation-dependent schedule overrides to an evaluation result.

    During the grace period, KILL decisions are softened to mutate_only so
    that Adam and early children can continue evolving. Fitness and failure
    labels are preserved for telemetry.

    Args:
        result: Original evaluation result
        schedule: Schedule configuration
        generation: Current generation index (0-based)

    Returns:
        Possibly modified StrategyEvaluationResult (new instance if changed)
    """
    if not schedule.is_grace_period(generation):
        return result

    if result.decision != "kill":
        return result

    if not schedule.mutate_on_kill_during_grace:
        return result

    # Grace period: soften kill -> mutate_only, preserve labels
    return StrategyEvaluationResult(
        graph_id=result.graph_id,
        strategy_name=result.strategy_name,
        validation_report=result.validation_report,
        fitness=result.fitness,
        decision="mutate_only",
        kill_reason=result.kill_reason,  # preserved for telemetry
    )


def get_survivors(results: List[StrategyEvaluationResult]) -> List[StrategyEvaluationResult]:
    """Filter evaluation results to survivors only.

    Args:
        results: List of StrategyEvaluationResults

    Returns:
        List containing only survivors (decision == "survive")
    """
    return [r for r in results if r.is_survivor()]


def rank_by_fitness(results: List[StrategyEvaluationResult]) -> List[StrategyEvaluationResult]:
    """Sort evaluation results by fitness (descending).

    Args:
        results: List of StrategyEvaluationResults

    Returns:
        Sorted list (highest fitness first)
    """
    return sorted(results, key=lambda r: r.fitness, reverse=True)
