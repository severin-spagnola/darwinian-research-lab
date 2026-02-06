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
class Phase3Config:
    enabled: bool = False
    mode: str = "baseline"  # "episodes" to enable Phase 3 sampling
    n_episodes: int = 8
    min_months: int = 6
    max_months: int = 12
    min_bars: int = 120
    seed: Optional[int] = None
    sampling_mode: str = "random"  # "random" or "stratified_by_regime"
    min_trades_per_episode: int = 3  # Minimum trades for valid episode
    regime_penalty_weight: float = 0.3  # Weight for single-regime dependence penalty
    abort_on_all_episode_failures: bool = True  # Raise error if all episodes fail (dev safety)


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
    **kwargs,
) -> StrategyEvaluationResult:
    """Phase 3 evaluation for episode-based robustness."""
    if not phase3_config or not phase3_config.enabled or phase3_config.mode != "episodes":
        return evaluate_strategy(strategy, data, initial_capital=initial_capital)

    aggregate = evaluate_strategy_on_episodes(
        strategy=strategy,
        data=data,
        n_episodes=phase3_config.n_episodes,
        min_months=phase3_config.min_months,
        max_months=phase3_config.max_months,
        min_bars=phase3_config.min_bars,
        seed=phase3_config.seed,
        initial_capital=initial_capital,
        sampling_mode=phase3_config.sampling_mode,
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
            "regime_coverage": aggregate.regime_coverage,
            "n_trades_per_episode": aggregate.n_trades_per_episode,
            "episodes": [
                {
                    "label": ep.episode_spec.label,
                    "start_ts": ep.episode_spec.start_ts.isoformat(),
                    "end_ts": ep.episode_spec.end_ts.isoformat(),
                    "fitness": round(ep.episode_fitness, 3),
                    "decision": ep.decision,
                    "kill_reason": ep.kill_reason,
                    "tags": ep.tags,
                    "error_details": ep.error_details,  # Include failure diagnostics
                    "debug_stats": ep.debug_stats,  # Include no-trade autopsy
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
