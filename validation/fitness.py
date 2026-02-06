"""Fitness scoring for strategy validation.

Combines performance metrics with anti-overfit penalties.
"""

from typing import Dict, Any


def calculate_base_score(metrics: Dict[str, Any]) -> float:
    """Calculate base performance score from backtest metrics.

    Formula: sharpe - 0.5 * max_drawdown_pct

    Args:
        metrics: Backtest metrics dict

    Returns:
        Base score (can be negative)
    """
    sharpe = metrics.get('sharpe_ratio', 0.0)
    max_dd_pct = abs(metrics.get('max_drawdown_pct', 0.0))

    score = sharpe - (0.5 * max_dd_pct)

    return score


def calculate_fitness(
    train_metrics: Dict[str, Any],
    holdout_metrics: Dict[str, Any],
    penalties: Dict[str, float],
) -> float:
    """Calculate final fitness score with train/holdout weighting and penalties.

    Formula: fitness = 0.2*train_score + 0.8*holdout_score - sum(penalties)

    Heavily weights holdout performance to discourage overfitting.

    Args:
        train_metrics: Training set backtest metrics
        holdout_metrics: Holdout set backtest metrics
        penalties: Dict of penalty name -> penalty value

    Returns:
        Final fitness score (higher is better, can be negative)
    """
    train_score = calculate_base_score(train_metrics)
    holdout_score = calculate_base_score(holdout_metrics)

    # Weight holdout heavily (80%)
    weighted_score = (0.2 * train_score) + (0.8 * holdout_score)

    # Subtract penalties
    total_penalty = sum(penalties.values())

    fitness = weighted_score - total_penalty

    return fitness


def extract_penalties(validation_results: Dict[str, Any]) -> Dict[str, float]:
    """Extract all penalties from validation results.

    Args:
        validation_results: Output from run_full_validation()

    Returns:
        Dict mapping penalty name -> value
    """
    penalties = {}

    # Stability penalties
    stability = validation_results.get('stability', {})
    if stability:
        penalties['concentration'] = stability.get('concentration_penalty', 0.0)
        penalties['cliff'] = stability.get('cliff_penalty', 0.0)

    # Fragility penalties
    fragility = validation_results.get('fragility', {})
    if fragility:
        penalties['sign_flip'] = fragility.get('sign_flip_penalty', 0.0)
        penalties['fragility'] = fragility.get('fragility_score', 0.0) * 0.5  # Scale down

    return penalties


def score_validation(validation_results: Dict[str, Any]) -> Dict[str, Any]:
    """Score a complete validation run.

    Args:
        validation_results: Output from run_full_validation()

    Returns:
        Dict with:
            - train_score: Base score on training set
            - holdout_score: Base score on holdout set
            - penalties: Dict of all penalties
            - total_penalty: Sum of penalties
            - fitness: Final fitness score
    """
    train_metrics = validation_results['train_results']['metrics']
    holdout_metrics = validation_results['holdout_results']['metrics']

    train_score = calculate_base_score(train_metrics)
    holdout_score = calculate_base_score(holdout_metrics)

    penalties = extract_penalties(validation_results)
    total_penalty = sum(penalties.values())

    fitness = calculate_fitness(train_metrics, holdout_metrics, penalties)

    return {
        'train_score': train_score,
        'holdout_score': holdout_score,
        'penalties': penalties,
        'total_penalty': total_penalty,
        'fitness': fitness,
    }
