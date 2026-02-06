"""Tests for Phase 3.2: adaptive selection pressure + Adam grace period."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from validation.evaluation import (
    Phase3ScheduleConfig,
    StrategyEvaluationResult,
    apply_schedule_override,
)


def _make_result(decision="kill", fitness=-0.5, kill_reason=None):
    """Helper to build a StrategyEvaluationResult."""
    return StrategyEvaluationResult(
        graph_id="test_graph",
        strategy_name="test",
        validation_report={},
        fitness=fitness,
        decision=decision,
        kill_reason=kill_reason or ["negative_fitness"],
    )


# --- Test 1: grace period prevents KILL but preserves labels ---

def test_grace_period_prevents_kill_preserves_labels():
    schedule = Phase3ScheduleConfig(grace_generations=2, mutate_on_kill_during_grace=True)

    killed = _make_result(decision="kill", fitness=-0.3, kill_reason=["negative_fitness", "no_holdout_trades"])

    # Generation 0 (within grace): should become mutate_only
    overridden = apply_schedule_override(killed, schedule, generation=0)
    assert overridden.decision == "mutate_only"
    assert overridden.fitness == -0.3  # fitness preserved
    assert "negative_fitness" in overridden.kill_reason  # labels preserved
    assert "no_holdout_trades" in overridden.kill_reason
    assert overridden.can_mutate()  # should be mutable

    # Generation 1 (still within grace_generations=2)
    overridden_g1 = apply_schedule_override(killed, schedule, generation=1)
    assert overridden_g1.decision == "mutate_only"

    # Generation 2 (past grace): should remain KILL
    not_overridden = apply_schedule_override(killed, schedule, generation=2)
    assert not_overridden.decision == "kill"
    assert not_overridden.kill_reason == ["negative_fitness", "no_holdout_trades"]


def test_grace_does_not_affect_survivors():
    schedule = Phase3ScheduleConfig(grace_generations=2)

    survived = _make_result(decision="survive", fitness=0.5, kill_reason=[])

    # Even during grace, survivors stay as survivors
    result = apply_schedule_override(survived, schedule, generation=0)
    assert result.decision == "survive"
    assert result.fitness == 0.5


def test_mutate_on_kill_during_grace_false():
    schedule = Phase3ScheduleConfig(grace_generations=2, mutate_on_kill_during_grace=False)

    killed = _make_result(decision="kill", fitness=-0.3)

    # Grace period but mutate_on_kill_during_grace=False: kill stays
    result = apply_schedule_override(killed, schedule, generation=0)
    assert result.decision == "kill"


# --- Test 2: schedule ramps min_holdout_trades and penalty weights ---

def test_schedule_ramps_min_holdout_trades():
    schedule = Phase3ScheduleConfig(
        min_holdout_trades_schedule=[0, 3, 10],
    )
    assert schedule.get_min_holdout_trades(0) == 0
    assert schedule.get_min_holdout_trades(1) == 3
    assert schedule.get_min_holdout_trades(2) == 10
    # Beyond list length: clamp to last value
    assert schedule.get_min_holdout_trades(5) == 10
    assert schedule.get_min_holdout_trades(100) == 10


def test_schedule_ramps_penalty_weights():
    schedule = Phase3ScheduleConfig(
        penalty_weight_schedule=[0.0, 0.5, 1.0],
    )
    assert schedule.get_penalty_weight(0) == 0.0
    assert schedule.get_penalty_weight(1) == 0.5
    assert schedule.get_penalty_weight(2) == 1.0
    # Beyond list: clamp to last
    assert schedule.get_penalty_weight(10) == 1.0


def test_schedule_ramps_holdout_weights():
    schedule = Phase3ScheduleConfig(
        holdout_weight_schedule=[0.6, 0.7, 0.8],
    )
    assert schedule.get_holdout_weight(0) == 0.6
    assert schedule.get_holdout_weight(1) == 0.7
    assert schedule.get_holdout_weight(2) == 0.8
    assert schedule.get_holdout_weight(99) == 0.8


def test_default_schedule_values():
    """Default schedule should be identity: full penalties, no grace override needed."""
    schedule = Phase3ScheduleConfig()
    assert schedule.grace_generations == 1
    assert schedule.get_min_holdout_trades(0) == 3
    assert schedule.get_penalty_weight(0) == 1.0
    assert schedule.get_holdout_weight(0) == 0.8
    assert schedule.is_grace_period(0) is True
    assert schedule.is_grace_period(1) is False


def test_schedule_serialization():
    schedule = Phase3ScheduleConfig(
        grace_generations=2,
        min_holdout_trades_schedule=[0, 5],
        penalty_weight_schedule=[0.0, 1.0],
    )
    d = schedule.to_dict()
    assert d["grace_generations"] == 2
    assert d["min_holdout_trades_schedule"] == [0, 5]
    assert d["penalty_weight_schedule"] == [0.0, 1.0]
    assert "mutate_on_kill_during_grace" in d


def test_can_mutate_for_different_decisions():
    """Verify can_mutate() returns True for survive and mutate_only."""
    survive = _make_result(decision="survive", fitness=0.5, kill_reason=[])
    assert survive.can_mutate()

    mutate_only = _make_result(decision="mutate_only", fitness=-0.1, kill_reason=["negative_fitness"])
    assert mutate_only.can_mutate()

    killed = _make_result(decision="kill", fitness=-0.5, kill_reason=["negative_fitness"])
    assert not killed.can_mutate()
