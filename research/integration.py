"""Integration layer for wiring research artifacts into Darwin evolution.

This module provides the hook that Darwin calls after each evaluation.
"""

from typing import Optional

from validation.evaluation import StrategyEvaluationResult, Phase3Config
from evolution.patches import PatchSet
from research.service import generate_and_save_artifacts
from research.storage import ResearchStorage


def save_research_artifacts(
    run_id: str,
    evaluation_result: StrategyEvaluationResult,
    phase3_config: Optional[Phase3Config] = None,
    parent_graph_id: Optional[str] = None,
    generation: Optional[int] = None,
    patch: Optional[PatchSet] = None,
) -> bool:
    """Generate and save Blue Memo + Red Verdict after evaluation.

    This is called from Darwin after saving the evaluation and phase3 report.

    Args:
        run_id: Run identifier
        evaluation_result: Strategy evaluation result
        phase3_config: Phase3 config (checks if memos/verdicts enabled)
        parent_graph_id: Parent graph ID (if mutation)
        generation: Generation index
        patch: PatchSet applied (if mutation)

    Returns:
        True if artifacts were generated, False if skipped
    """
    # Check if memos/verdicts generation is enabled
    if phase3_config and not phase3_config.generate_memos_verdicts:
        return False

    try:
        generate_and_save_artifacts(
            run_id=run_id,
            evaluation_result=evaluation_result,
            parent_graph_id=parent_graph_id,
            generation=generation,
            patch=patch,
        )
        return True
    except Exception:
        # Fail gracefully - don't crash Darwin if artifact generation fails
        return False


def check_research_trigger(
    run_id: str,
    graph_id: str,
    phase3_config: Optional[Phase3Config] = None,
) -> Optional[str]:
    """Check if this kill should trigger research.

    Args:
        run_id: Run identifier
        graph_id: Graph identifier
        phase3_config: Phase3 config (contains research budget + triggers)

    Returns:
        Query string if research should be triggered, None otherwise
    """
    if not phase3_config or phase3_config.research_budget_per_generation <= 0:
        return None

    # Load Red Verdict to check failure codes
    storage = ResearchStorage(run_id=run_id)
    verdict = storage.load_red_verdict(graph_id)

    if not verdict or verdict.verdict != "KILL":
        return None

    # Check if any top failures match research trigger codes
    if not phase3_config.research_on_kill_reasons:
        return None

    for failure in verdict.top_failures:
        if failure.code in phase3_config.research_on_kill_reasons:
            # Build targeted query
            query = f"algorithmic trading {failure.code.lower().replace('_', ' ')} solutions"
            return query

    return None
