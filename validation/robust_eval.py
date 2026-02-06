"""Robust multi-symbol and multi-timeframe evaluation.

Prevents overfitting to single ticker or timeframe.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Any
from dataclasses import dataclass

from graph.schema import StrategyGraph
from validation.overfit_tests import run_full_validation
from validation.fitness import score_validation
from validation.reporting import ValidationReport, create_validation_report
from validation.evaluation import StrategyEvaluationResult


@dataclass
class RobustEvaluationResult:
    """Result of robust multi-symbol/timeframe evaluation."""
    graph_id: str
    strategy_name: str

    # Aggregated metrics
    median_fitness: float
    worst_fitness: float
    best_fitness: float
    fitness_dispersion: float

    # Per-symbol/timeframe results
    per_symbol_fitness: Dict[str, float]
    per_timeframe_fitness: Dict[str, float]

    # Worst case info
    worst_symbol: str
    worst_timeframe: str

    # Decision
    decision: str
    kill_reason: List[str]

    # Full validation report (aggregated)
    validation_report: Dict[str, Any]


def evaluate_strategy_robust(
    strategy: StrategyGraph,
    data_dict: Dict[str, pd.DataFrame],  # symbol -> bars_df
    timeframes: List[str] = None,  # If None, use strategy's timeframe
    train_frac: float = 0.75,
    k_windows: int = 6,
    n_jitter: int = 10,
    jitter_pct: float = 0.1,
    initial_capital: float = 100000.0,
    worst_symbol_threshold: float = -0.5,
) -> RobustEvaluationResult:
    """Evaluate strategy across multiple symbols and optionally timeframes.

    Args:
        strategy: StrategyGraph to evaluate
        data_dict: Dict mapping symbol -> OHLCV DataFrame
        timeframes: Optional list of timeframes to test (must have data for each)
        train_frac: Train/holdout split
        k_windows: Subwindows for stability
        n_jitter: Parameter jitter runs
        jitter_pct: Jitter percentage
        initial_capital: Starting capital
        worst_symbol_threshold: Threshold for worst_symbol_penalty

    Returns:
        RobustEvaluationResult with aggregated metrics
    """
    # For Phase 6.5 MVP, keep it simple: evaluate on each symbol with strategy's timeframe
    # Timeframe sweep would require re-fetching data for each timeframe

    if timeframes is not None:
        # TODO: Implement timeframe sweep
        # Would need to fetch data for each timeframe and evaluate
        raise NotImplementedError("Timeframe sweep not yet implemented")

    # Evaluate on each symbol
    symbol_results = {}

    for symbol, data in data_dict.items():
        print(f"  Evaluating on {symbol}...")

        # Run full validation
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

        symbol_results[symbol] = {
            'validation': validation_results,
            'fitness': fitness_results,
            'holdout_score': fitness_results['holdout_score'],
        }

    # Aggregate results
    holdout_scores = np.array([r['holdout_score'] for r in symbol_results.values()])
    fitness_scores = np.array([r['fitness']['fitness'] for r in symbol_results.values()])

    median_fitness = np.median(fitness_scores)
    worst_fitness = np.min(fitness_scores)
    best_fitness = np.max(fitness_scores)
    fitness_dispersion = np.std(fitness_scores)

    # Find worst symbol
    worst_idx = np.argmin(fitness_scores)
    worst_symbol = list(symbol_results.keys())[worst_idx]

    # Calculate penalties
    penalties = {}

    # Worst symbol penalty
    if worst_fitness < worst_symbol_threshold:
        worst_symbol_penalty = abs(worst_fitness - worst_symbol_threshold)
        penalties['worst_symbol'] = worst_symbol_penalty

    # Dispersion penalty (high variance across symbols)
    if fitness_dispersion > 0.3:
        penalties['symbol_dispersion'] = fitness_dispersion

    # Final aggregated fitness (median with penalties)
    aggregated_fitness = median_fitness - sum(penalties.values())

    # Decision logic (use worst_symbol's failure labels + aggregated penalties)
    worst_symbol_result = symbol_results[worst_symbol]
    worst_report = create_validation_report(
        strategy_id=strategy.graph_id,
        strategy_name=strategy.name,
        validation_results=worst_symbol_result['validation'],
        fitness_results=worst_symbol_result['fitness'],
    )

    failure_labels = worst_report.get_failure_labels()

    # Add multi-symbol specific failures
    if worst_fitness < worst_symbol_threshold:
        failure_labels.append("failed_on_symbol")

    # Apply survival gate
    decision, kill_reason = _apply_robust_survival_gate(failure_labels, aggregated_fitness)

    # Build aggregated validation report
    # Use median symbol's results as representative
    median_idx = np.argsort(fitness_scores)[len(fitness_scores) // 2]
    median_symbol = list(symbol_results.keys())[median_idx]
    median_result = symbol_results[median_symbol]

    median_report = create_validation_report(
        strategy_id=strategy.graph_id,
        strategy_name=strategy.name,
        validation_results=median_result['validation'],
        fitness_results=median_result['fitness'],
    )

    validation_report_dict = median_report.to_dict()
    validation_report_dict['multi_symbol'] = {
        'median_fitness': round(median_fitness, 3),
        'worst_fitness': round(worst_fitness, 3),
        'worst_symbol': worst_symbol,
        'dispersion': round(fitness_dispersion, 3),
        'penalties': {k: round(v, 3) for k, v in penalties.items()},
    }

    return RobustEvaluationResult(
        graph_id=strategy.graph_id,
        strategy_name=strategy.name,
        median_fitness=aggregated_fitness,
        worst_fitness=worst_fitness,
        best_fitness=best_fitness,
        fitness_dispersion=fitness_dispersion,
        per_symbol_fitness={s: r['fitness']['fitness'] for s, r in symbol_results.items()},
        per_timeframe_fitness={},  # TODO: Implement timeframe sweep
        worst_symbol=worst_symbol,
        worst_timeframe="",  # TODO
        decision=decision,
        kill_reason=kill_reason,
        validation_report=validation_report_dict,
    )


def _apply_robust_survival_gate(
    failure_labels: List[str], fitness: float
) -> tuple[str, List[str]]:
    """Apply survival gate for robust evaluation."""
    kill_reasons = []

    # Same rules as standard gate plus multi-symbol failures
    if fitness < 0:
        kill_reasons.append("negative_fitness")

    if "no_holdout_trades" in failure_labels:
        kill_reasons.append("no_holdout_trades")

    if "too_few_holdout_trades" in failure_labels:
        kill_reasons.append("too_few_holdout_trades")

    if "severe_holdout_degradation" in failure_labels:
        kill_reasons.append("severe_holdout_degradation")

    if "failed_on_symbol" in failure_labels:
        kill_reasons.append("failed_on_symbol")

    if kill_reasons:
        return "kill", kill_reasons
    else:
        return "survive", []
