"""Validation reporting for LLM consumption.

Produces compact, standardized JSON reports for strategy validation.
"""

import json
from typing import Dict, Any, List
from datetime import datetime
from pathlib import Path

import config


class ValidationReport:
    """Standardized validation report for LLM consumption."""

    def __init__(
        self,
        strategy_id: str,
        strategy_name: str,
        train_metrics: Dict[str, Any],
        holdout_metrics: Dict[str, Any],
        stability: Dict[str, Any],
        fragility: Dict[str, Any],
        penalties: Dict[str, float],
        fitness: float,
    ):
        self.strategy_id = strategy_id
        self.strategy_name = strategy_name
        self.train_metrics = train_metrics
        self.holdout_metrics = holdout_metrics
        self.stability = stability
        self.fragility = fragility
        self.penalties = penalties
        self.fitness = fitness
        self.timestamp = datetime.now().isoformat()

    def get_failure_labels(self) -> List[str]:
        """Generate failure labels based on validation results.

        Returns:
            List of failure labels (empty if strategy passes all tests)
        """
        labels = []

        # Check train vs holdout degradation
        train_return = self.train_metrics.get('total_return_pct', 0.0)
        holdout_return = self.holdout_metrics.get('total_return_pct', 0.0)

        if train_return > 0.05 and holdout_return < 0:
            labels.append("holdout_sign_flip")

        if train_return > 0 and holdout_return < (train_return * 0.3):
            labels.append("severe_holdout_degradation")

        # Check penalties
        if self.penalties.get('concentration', 0.0) > 0.5:
            labels.append("concentrated_returns")

        if self.penalties.get('cliff', 0.0) > 0.5:
            labels.append("performance_cliff")

        if self.penalties.get('sign_flip', 0.0) > 0.2:
            labels.append("parameter_fragile")

        if self.penalties.get('fragility', 0.0) > 0.5:
            labels.append("high_fragility")

        # Check if no trades
        if self.holdout_metrics.get('trade_count', 0) == 0:
            labels.append("no_holdout_trades")

        # Check too few holdout trades (Phase 6.5 robustness)
        if 0 < self.holdout_metrics.get('trade_count', 0) < 10:
            labels.append("too_few_holdout_trades")

        # Check too few holdout days (Phase 6.5 robustness)
        # This would require trade log with dates - stub for now
        # TODO: Add unique_trading_days to metrics
        # if self.holdout_metrics.get('unique_trading_days', 0) < 3:
        #     labels.append("too_few_holdout_days")

        # Check negative fitness
        if self.fitness < 0:
            labels.append("negative_fitness")

        return labels

    def to_dict(self) -> Dict[str, Any]:
        """Convert report to dictionary.

        Returns:
            Dict suitable for JSON serialization
        """
        # Compact train metrics (only key values)
        train_compact = {
            'return_pct': round(self.train_metrics.get('total_return_pct', 0.0), 4),
            'sharpe': round(self.train_metrics.get('sharpe_ratio', 0.0), 2),
            'max_dd_pct': round(self.train_metrics.get('max_drawdown_pct', 0.0), 4),
            'trades': self.train_metrics.get('trade_count', 0),
            'win_rate': round(self.train_metrics.get('win_rate', 0.0), 2),
        }

        # Compact holdout metrics
        holdout_compact = {
            'return_pct': round(self.holdout_metrics.get('total_return_pct', 0.0), 4),
            'sharpe': round(self.holdout_metrics.get('sharpe_ratio', 0.0), 2),
            'max_dd_pct': round(self.holdout_metrics.get('max_drawdown_pct', 0.0), 4),
            'trades': self.holdout_metrics.get('trade_count', 0),
            'win_rate': round(self.holdout_metrics.get('win_rate', 0.0), 2),
        }

        # Compact stability metrics
        stability_compact = {
            'concentration_penalty': round(self.stability.get('concentration_penalty', 0.0), 3),
            'cliff_penalty': round(self.stability.get('cliff_penalty', 0.0), 3),
            'consistency_score': round(self.stability.get('consistency_score', 0.0), 3),
        }

        # Compact fragility metrics
        fragility_compact = {
            'return_dispersion': round(self.fragility.get('return_dispersion', 0.0), 2),
            'sign_flip_penalty': round(self.fragility.get('sign_flip_penalty', 0.0), 3),
            'fragility_score': round(self.fragility.get('fragility_score', 0.0), 3),
        }

        return {
            'strategy_id': self.strategy_id,
            'strategy_name': self.strategy_name,
            'timestamp': self.timestamp,
            'train_metrics': train_compact,
            'holdout_metrics': holdout_compact,
            'stability': stability_compact,
            'fragility': fragility_compact,
            'penalties': {k: round(v, 3) for k, v in self.penalties.items()},
            'failure_labels': self.get_failure_labels(),
            'fitness': round(self.fitness, 3),
        }

    def to_json(self, indent: int = 2) -> str:
        """Convert report to JSON string.

        Args:
            indent: JSON indentation level

        Returns:
            JSON string
        """
        return json.dumps(self.to_dict(), indent=indent)

    def save(self, filename: str = None) -> Path:
        """Save report to results directory.

        Args:
            filename: Optional filename (default: {strategy_id}_validation.json)

        Returns:
            Path to saved file
        """
        if filename is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{self.strategy_id}_validation_{timestamp}.json"

        filepath = config.RESULTS_DIR / filename

        with open(filepath, 'w') as f:
            f.write(self.to_json())

        return filepath


def create_validation_report(
    strategy_id: str,
    strategy_name: str,
    validation_results: Dict[str, Any],
    fitness_results: Dict[str, Any],
) -> ValidationReport:
    """Create ValidationReport from validation and fitness results.

    Args:
        strategy_id: Strategy graph ID
        strategy_name: Strategy name
        validation_results: Output from run_full_validation()
        fitness_results: Output from score_validation()

    Returns:
        ValidationReport instance
    """
    return ValidationReport(
        strategy_id=strategy_id,
        strategy_name=strategy_name,
        train_metrics=validation_results['train_results']['metrics'],
        holdout_metrics=validation_results['holdout_results']['metrics'],
        stability=validation_results['stability'],
        fragility=validation_results['fragility'],
        penalties=fitness_results['penalties'],
        fitness=fitness_results['fitness'],
    )
