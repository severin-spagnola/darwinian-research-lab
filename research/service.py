"""Service layer for generating Blue Memos and Red Verdicts from evaluations.

This module wires evaluation results into the research artifact layer.
"""

from typing import Optional, List, Dict, Any

from research.models import BlueMemo, RedVerdict
from research.storage import ResearchStorage
from validation.evaluation import StrategyEvaluationResult
from evolution.patches import PatchSet


def generate_and_save_artifacts(
    run_id: str,
    evaluation_result: StrategyEvaluationResult,
    parent_graph_id: Optional[str] = None,
    generation: Optional[int] = None,
    patch: Optional[PatchSet] = None,
) -> tuple[BlueMemo, RedVerdict]:
    """Generate Blue Memo and Red Verdict from evaluation, then persist.

    Args:
        run_id: Run identifier
        evaluation_result: Strategy evaluation result
        parent_graph_id: Parent graph ID (if mutation)
        generation: Generation index
        patch: PatchSet applied (if mutation)

    Returns:
        (BlueMemo, RedVerdict) tuple
    """
    storage = ResearchStorage(run_id=run_id)
    graph_id = evaluation_result.graph_id

    # Extract patch summary
    patch_summary = _extract_patch_summary(patch) if patch else []

    # Extract Phase3 report if available
    phase3_report = None
    if "phase3" in evaluation_result.validation_report:
        phase3_report = evaluation_result.validation_report

    # Generate Blue Memo
    memo = BlueMemo.from_evaluation(
        run_id=run_id,
        graph_id=graph_id,
        parent_graph_id=parent_graph_id,
        generation=generation,
        patch_summary=patch_summary,
        phase3_report=phase3_report,
    )

    # Generate Red Verdict
    verdict = RedVerdict.from_evaluation(
        run_id=run_id,
        graph_id=graph_id,
        evaluation_result=evaluation_result,
        phase3_report=phase3_report,
    )

    # Persist both
    storage.save_blue_memo(memo)
    storage.save_red_verdict(verdict)

    return memo, verdict


def _extract_patch_summary(patch: PatchSet) -> List[str]:
    """Extract human-readable summary from PatchSet.

    Deterministic - no LLM.
    """
    summary = []

    for op in patch.ops:
        if op.op_type == "add_node":
            node_type = op.new_node.get("type", "unknown")
            summary.append(f"add_node: {node_type}")

        elif op.op_type == "remove_node":
            summary.append(f"remove_node: {op.node_id}")

        elif op.op_type == "modify_param":
            summary.append(
                f"modify_param: {op.node_id}.{op.param_name} = {op.param_value}"
            )

        elif op.op_type == "rewire":
            source = "->".join(op.new_source) if op.new_source else "none"
            summary.append(f"rewire: {op.node_id}.{op.input_name} <- {source}")

    return summary


def load_artifacts_for_graph(
    run_id: str, graph_id: str
) -> tuple[Optional[BlueMemo], Optional[RedVerdict]]:
    """Load Blue Memo and Red Verdict for a graph.

    Args:
        run_id: Run identifier
        graph_id: Graph identifier

    Returns:
        (BlueMemo, RedVerdict) tuple (either may be None if not found)
    """
    storage = ResearchStorage(run_id=run_id)
    memo = storage.load_blue_memo(graph_id)
    verdict = storage.load_red_verdict(graph_id)
    return memo, verdict
