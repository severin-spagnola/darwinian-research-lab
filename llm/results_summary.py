"""Compact results summary for LLM consumption.

Produces minimal JSON (~2KB) from StrategyEvaluationResult for efficient LLM context.
"""

from typing import Dict, Any
from validation.evaluation import StrategyEvaluationResult


def create_results_summary(result: StrategyEvaluationResult) -> Dict[str, Any]:
    """Create compact ResultsSummary from StrategyEvaluationResult.

    Designed to be <2KB JSON for efficient LLM context usage.
    Excludes large arrays (equity curves, full trade logs).

    Args:
        result: StrategyEvaluationResult from evaluate_strategy()

    Returns:
        Compact dict with key metrics, penalties, and decision
    """
    report = result.validation_report

    # Extract compact metrics
    train = report.get('train_metrics', {})
    holdout = report.get('holdout_metrics', {})
    stability = report.get('stability', {})
    fragility = report.get('fragility', {})
    penalties = report.get('penalties', {})

    # Sort penalties by value (highest first)
    top_penalties = dict(sorted(penalties.items(), key=lambda x: x[1], reverse=True)[:3])

    summary = {
        'graph_id': result.graph_id,
        'strategy_name': result.strategy_name,
        'decision': result.decision,
        'fitness': round(result.fitness, 3),
        'kill_reason': result.kill_reason,
        'failure_labels': report.get('failure_labels', []),

        'train': {
            'return_pct': round(train.get('return_pct', 0.0), 4),
            'sharpe': round(train.get('sharpe', 0.0), 2),
            'max_dd_pct': round(train.get('max_dd_pct', 0.0), 4),
            'trades': train.get('trades', 0),
            'win_rate': round(train.get('win_rate', 0.0), 2),
        },

        'holdout': {
            'return_pct': round(holdout.get('return_pct', 0.0), 4),
            'sharpe': round(holdout.get('sharpe', 0.0), 2),
            'max_dd_pct': round(holdout.get('max_dd_pct', 0.0), 4),
            'trades': holdout.get('trades', 0),
            'win_rate': round(holdout.get('win_rate', 0.0), 2),
        },

        'top_penalties': top_penalties,

        'stability': {
            'concentration': round(stability.get('concentration_penalty', 0.0), 3),
            'cliff': round(stability.get('cliff_penalty', 0.0), 3),
            'consistency': round(stability.get('consistency_score', 0.0), 3),
        },

        'fragility': {
            'dispersion': round(fragility.get('return_dispersion', 0.0), 2),
            'sign_flip': round(fragility.get('sign_flip_penalty', 0.0), 3),
            'score': round(fragility.get('fragility_score', 0.0), 3),
        },
    }

    return summary


def create_batch_summary(results: list[StrategyEvaluationResult]) -> Dict[str, Any]:
    """Create compact summary for batch of strategies.

    Args:
        results: List of StrategyEvaluationResults

    Returns:
        Compact batch summary with ranked results
    """
    survivors = [r for r in results if r.is_survivor()]
    killed = [r for r in results if r.decision == "kill"]

    # Sort by fitness
    ranked = sorted(results, key=lambda r: r.fitness, reverse=True)

    summary = {
        'total': len(results),
        'survivors': len(survivors),
        'killed': len(killed),
        'best_fitness': ranked[0].fitness if ranked else 0.0,
        'worst_fitness': ranked[-1].fitness if ranked else 0.0,
        'strategies': [
            {
                'graph_id': r.graph_id,
                'decision': r.decision,
                'fitness': round(r.fitness, 3),
                'kill_reason': r.kill_reason[:2] if r.kill_reason else [],  # Top 2 reasons
            }
            for r in ranked
        ]
    }

    return summary
