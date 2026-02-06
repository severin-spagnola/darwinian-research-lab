"""Anti-overfitting validation tests.

Implements brutal validation suite:
- Time holdout split (train vs holdout)
- Subwindow stability (K chunks, cliff detection)
- Parameter jitter (sensitivity testing)
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, List, Tuple
from copy import deepcopy

from graph.schema import StrategyGraph, Node
from graph.executor import GraphExecutor
from backtest.simulator import run_backtest


def time_holdout_split(
    data: pd.DataFrame, train_frac: float = 0.75
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Split data into train and holdout sets chronologically.

    Args:
        data: Full OHLCV DataFrame
        train_frac: Fraction of data for training (default 0.75 = 75%)

    Returns:
        (train_data, holdout_data)
    """
    split_idx = int(len(data) * train_frac)

    # Preserve index (especially timestamp index needed for Phase 3)
    train_data = data.iloc[:split_idx].copy()
    holdout_data = data.iloc[split_idx:].copy()

    return train_data, holdout_data


def run_backtest_on_data(
    strategy: StrategyGraph, data: pd.DataFrame, initial_capital: float = 100000.0
) -> Dict[str, Any]:
    """Execute strategy and run backtest on given data.

    Args:
        strategy: StrategyGraph to test
        data: OHLCV DataFrame
        initial_capital: Starting capital

    Returns:
        Results dict with trades, equity_curve, metrics
    """
    executor = GraphExecutor()
    context = executor.execute(strategy, data)

    # Get orders config from last output
    orders_key = list(strategy.outputs.values())[0]
    orders_config = context[orders_key]

    results = run_backtest(data=data, orders_config=orders_config, initial_capital=initial_capital)

    return results


def subwindow_stability(
    strategy: StrategyGraph, data: pd.DataFrame, k: int = 6, initial_capital: float = 100000.0
) -> Dict[str, Any]:
    """Test strategy stability across K chronological subwindows.

    Detects:
    - Concentration: Most returns from single window
    - Cliffs: Performance degradation in later windows
    - Inconsistency: High variance across windows

    Args:
        strategy: StrategyGraph to test
        data: Full OHLCV DataFrame
        k: Number of chunks to split data into (default 6)
        initial_capital: Starting capital per window

    Returns:
        Dict with:
            - window_results: List of metrics per window
            - concentration_penalty: Score for return concentration
            - cliff_penalty: Score for performance degradation
            - consistency_score: 1 - (std / mean) of returns
    """
    chunk_size = len(data) // k
    window_results = []

    for i in range(k):
        start_idx = i * chunk_size
        end_idx = start_idx + chunk_size if i < k - 1 else len(data)

        window_data = data.iloc[start_idx:end_idx].reset_index(drop=True)

        try:
            results = run_backtest_on_data(strategy, window_data, initial_capital)
            window_results.append({
                'window': i,
                'trades': results['metrics']['trade_count'],
                'return': results['metrics']['total_return'],
                'return_pct': results['metrics']['total_return_pct'],
                'sharpe': results['metrics']['sharpe_ratio'],
                'max_dd_pct': results['metrics']['max_drawdown_pct'],
            })
        except Exception as e:
            # Window failed (e.g., no trades, error in execution)
            window_results.append({
                'window': i,
                'trades': 0,
                'return': 0.0,
                'return_pct': 0.0,
                'sharpe': 0.0,
                'max_dd_pct': 0.0,
                'error': str(e)
            })

    # Calculate concentration penalty
    returns = np.array([w['return'] for w in window_results])
    total_return = returns.sum()

    if total_return > 0:
        return_shares = returns / total_return
        # Concentration: If one window dominates, penalty is high
        max_share = return_shares.max()
        concentration_penalty = max(0, max_share - (1.0 / k)) * 2.0  # Scale penalty
    else:
        concentration_penalty = 0.0

    # Calculate cliff penalty (performance degradation)
    # Compare first half vs second half
    first_half_returns = returns[:k//2].mean()
    second_half_returns = returns[k//2:].mean()

    if first_half_returns > 0:
        degradation = (first_half_returns - second_half_returns) / abs(first_half_returns)
        cliff_penalty = max(0, degradation) * 2.0  # Penalty if second half worse
    else:
        cliff_penalty = 0.0

    # Calculate consistency score
    if len(returns) > 1 and returns.mean() != 0:
        consistency_score = 1.0 - (returns.std() / abs(returns.mean()))
        consistency_score = max(0, consistency_score)  # Clamp to [0, inf)
    else:
        consistency_score = 0.0

    return {
        'window_results': window_results,
        'concentration_penalty': concentration_penalty,
        'cliff_penalty': cliff_penalty,
        'consistency_score': consistency_score,
    }


def parameter_jitter(
    strategy: StrategyGraph,
    data: pd.DataFrame,
    n: int = 10,
    jitter: float = 0.1,
    initial_capital: float = 100000.0
) -> Dict[str, Any]:
    """Test strategy robustness to parameter perturbations.

    Jitters numeric parameters by ±jitter% and re-runs holdout test.
    Detects fragility: small parameter changes cause large metric swings.

    Args:
        strategy: StrategyGraph to test
        data: Holdout OHLCV DataFrame
        n: Number of jitter runs (default 10)
        jitter: Jitter fraction (default 0.1 = ±10%)
        initial_capital: Starting capital

    Returns:
        Dict with:
            - baseline_metrics: Original strategy metrics
            - jittered_results: List of metrics from jittered runs
            - return_dispersion: Std dev of returns across jitters
            - sign_flip_penalty: Penalty if returns change sign
            - fragility_score: Overall fragility metric
    """
    # Run baseline
    try:
        baseline_results = run_backtest_on_data(strategy, data, initial_capital)
        baseline_return = baseline_results['metrics']['total_return']
        baseline_sharpe = baseline_results['metrics']['sharpe_ratio']
    except Exception as e:
        return {
            'baseline_metrics': None,
            'jittered_results': [],
            'return_dispersion': 0.0,
            'sign_flip_penalty': 0.0,
            'fragility_score': 1.0,  # Max fragility if baseline fails
            'error': str(e)
        }

    jittered_results = []

    for i in range(n):
        # Create jittered copy of strategy
        jittered_strategy = _jitter_strategy_params(strategy, jitter)

        try:
            results = run_backtest_on_data(jittered_strategy, data, initial_capital)
            jittered_results.append({
                'run': i,
                'return': results['metrics']['total_return'],
                'return_pct': results['metrics']['total_return_pct'],
                'sharpe': results['metrics']['sharpe_ratio'],
                'trades': results['metrics']['trade_count'],
            })
        except Exception as e:
            jittered_results.append({
                'run': i,
                'return': 0.0,
                'return_pct': 0.0,
                'sharpe': 0.0,
                'trades': 0,
                'error': str(e)
            })

    # Calculate dispersion
    returns = np.array([r['return'] for r in jittered_results])
    return_dispersion = returns.std() if len(returns) > 0 else 0.0

    # Calculate sign flip penalty
    baseline_sign = np.sign(baseline_return)
    sign_flips = sum(1 for r in returns if np.sign(r) != baseline_sign)
    sign_flip_penalty = (sign_flips / n) * 0.5 if n > 0 else 0.0

    # Fragility score: normalized dispersion
    if abs(baseline_return) > 0:
        fragility_score = return_dispersion / abs(baseline_return)
    else:
        fragility_score = 1.0 if return_dispersion > 0 else 0.0

    return {
        'baseline_metrics': {
            'return': baseline_return,
            'sharpe': baseline_sharpe,
        },
        'jittered_results': jittered_results,
        'return_dispersion': return_dispersion,
        'sign_flip_penalty': sign_flip_penalty,
        'fragility_score': fragility_score,
    }


def _jitter_strategy_params(strategy: StrategyGraph, jitter: float) -> StrategyGraph:
    """Create a copy of strategy with jittered parameters.

    Args:
        strategy: Original StrategyGraph
        jitter: Jitter fraction (e.g., 0.1 = ±10%)

    Returns:
        New StrategyGraph with jittered numeric params
    """
    jittered_strategy = deepcopy(strategy)

    for node in jittered_strategy.nodes:
        for param_name, param_value in node.params.items():
            # Only jitter numeric params
            if isinstance(param_value, (int, float)):
                # Jitter by ±jitter%
                jitter_amount = param_value * jitter * np.random.uniform(-1, 1)

                if isinstance(param_value, int):
                    # For integers (e.g., periods), round and enforce minimum of 2
                    new_value = int(round(param_value + jitter_amount))
                    new_value = max(2, new_value)  # Ensure periods >= 2
                else:
                    # For floats, just add jitter
                    new_value = param_value + jitter_amount
                    new_value = max(0.01, new_value)  # Ensure positive

                node.params[param_name] = new_value

    return jittered_strategy


def run_full_validation(
    strategy: StrategyGraph,
    data: pd.DataFrame,
    train_frac: float = 0.75,
    k_windows: int = 6,
    n_jitter: int = 10,
    jitter_pct: float = 0.1,
    initial_capital: float = 100000.0
) -> Dict[str, Any]:
    """Run complete validation suite.

    Args:
        strategy: StrategyGraph to validate
        data: Full OHLCV DataFrame
        train_frac: Train/holdout split fraction
        k_windows: Number of subwindows for stability test
        n_jitter: Number of parameter jitter runs
        jitter_pct: Jitter percentage
        initial_capital: Starting capital

    Returns:
        Dict with all validation results
    """
    # Split data
    train_data, holdout_data = time_holdout_split(data, train_frac)

    # Run on train set
    train_results = run_backtest_on_data(strategy, train_data, initial_capital)

    # Run on holdout set
    holdout_results = run_backtest_on_data(strategy, holdout_data, initial_capital)

    # Subwindow stability (on full data)
    stability = subwindow_stability(strategy, data, k_windows, initial_capital)

    # Parameter jitter (on holdout data)
    fragility = parameter_jitter(strategy, holdout_data, n_jitter, jitter_pct, initial_capital)

    return {
        'train_results': train_results,
        'holdout_results': holdout_results,
        'stability': stability,
        'fragility': fragility,
    }
