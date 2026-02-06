"""Population management utilities for Darwin evolution."""

from typing import List, Dict, Any
from collections import Counter

from validation.evaluation import StrategyEvaluationResult


def rank_by_fitness(results: List[StrategyEvaluationResult]) -> List[StrategyEvaluationResult]:
    """Sort evaluation results by fitness (descending).

    Args:
        results: List of StrategyEvaluationResults

    Returns:
        Sorted list (highest fitness first)
    """
    return sorted(results, key=lambda r: r.fitness, reverse=True)


def get_survivors(results: List[StrategyEvaluationResult]) -> List[StrategyEvaluationResult]:
    """Filter to survivors only.

    Args:
        results: List of StrategyEvaluationResults

    Returns:
        List containing only survivors (decision == "survive")
    """
    return [r for r in results if r.is_survivor()]


def prune_top_k(results: List[StrategyEvaluationResult], k: int) -> List[StrategyEvaluationResult]:
    """Prune to top K survivors by fitness.

    Args:
        results: List of StrategyEvaluationResults
        k: Number to keep

    Returns:
        Top K survivors sorted by fitness
    """
    survivors = get_survivors(results)
    ranked = rank_by_fitness(survivors)
    return ranked[:k]


def kill_stats_by_label(results: List[StrategyEvaluationResult]) -> Dict[str, int]:
    """Count kill reasons across all results.

    Args:
        results: List of StrategyEvaluationResults

    Returns:
        Dict mapping kill reason -> count (sorted descending)
    """
    all_reasons = []
    for result in results:
        if result.decision == "kill":
            all_reasons.extend(result.kill_reason)

    counts = Counter(all_reasons)
    return dict(counts.most_common())


def get_generation_stats(results: List[StrategyEvaluationResult]) -> Dict[str, Any]:
    """Get summary statistics for a generation.

    Args:
        results: List of StrategyEvaluationResults

    Returns:
        Dict with generation statistics
    """
    if not results:
        return {
            'total': 0,
            'survivors': 0,
            'killed': 0,
            'survivor_rate': 0.0,
            'best_fitness': 0.0,
            'mean_fitness': 0.0,
        }

    survivors = get_survivors(results)
    killed = [r for r in results if r.decision == "kill"]

    fitness_values = [r.fitness for r in results]

    return {
        'total': len(results),
        'survivors': len(survivors),
        'killed': len(killed),
        'survivor_rate': len(survivors) / len(results),
        'best_fitness': max(fitness_values),
        'worst_fitness': min(fitness_values),
        'mean_fitness': sum(fitness_values) / len(fitness_values),
    }
