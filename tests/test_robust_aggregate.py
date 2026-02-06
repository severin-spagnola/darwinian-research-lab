import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
from validation.robust_fitness import evaluate_strategy_on_episodes
from validation.evaluation import StrategyEvaluationResult


def test_robust_aggregate_penalties(monkeypatch):
    dates = pd.date_range("2020-01-01", periods=400, freq="D")
    df = pd.DataFrame({
        "open": range(400),
        "high": range(1, 401),
        "low": range(0, 400),
        "close": range(400),
    }, index=dates)

    fitness_sequence = [0.5, -0.8, 0.2]
    call_idx = {"count": 0}

    def fake_evaluate(strategy, data, initial_capital=100000.0):
        idx = call_idx["count"]
        call_idx["count"] += 1
        return StrategyEvaluationResult(
            graph_id="test",
            strategy_name="test",
            validation_report={},
            fitness=fitness_sequence[idx % len(fitness_sequence)],
            decision="survive",
            kill_reason=[],
        )

    monkeypatch.setattr("validation.evaluation.evaluate_strategy", fake_evaluate)

    aggregate = evaluate_strategy_on_episodes(
        strategy=None,
        data=df,
        n_episodes=3,
        min_months=1,
        max_months=1,
        min_bars=5,
        seed=1,
        initial_capital=100000.0,
    )

    assert aggregate.median_fitness == 0.2
    assert aggregate.worst_fitness == -0.8
    assert aggregate.best_fitness == 0.5
    assert aggregate.worst_case_penalty > 0
    assert aggregate.dispersion_penalty > 0
