"""Strategy mutation via LLM-proposed patches.

Generates child strategies from survivors using LLM-guided mutations.
"""

import json
from datetime import datetime
from typing import List, Dict, Any, Optional

from graph.schema import StrategyGraph
from graph.gene_pool import get_registry
from evolution.patches import PatchSet
from llm import client_openai, client_anthropic


def propose_child_patches(
    parent_graph: StrategyGraph,
    results_summary: Dict[str, Any],
    allowed_nodes: List[str] = None,
    allowed_patch_ops: List[str] = None,
    num_children: int = 3,
    provider: str = "anthropic",
    temperature: float = 0.8,
    run_id: Optional[str] = None,
) -> List[PatchSet]:
    """Propose mutation patches to create child strategies.

    IMPORTANT: Patches must NOT modify universe, time_config, or date_range.

    Args:
        parent_graph: Survivor StrategyGraph to mutate
        results_summary: Compact ResultsSummary dict (from create_results_summary)
        allowed_nodes: List of allowed node types (default: all)
        allowed_patch_ops: Allowed operations (default: all)
        num_children: Number of child patches to generate (default 3)
        provider: "openai" or "anthropic"
        temperature: LLM temperature

    Returns:
        List of PatchSet objects (one per child)

    Raises:
        ValidationError: If LLM output is invalid
    """
    registry = get_registry()

    if allowed_nodes is None:
        allowed_nodes = registry.get_all_types()

    if allowed_patch_ops is None:
        allowed_patch_ops = ["add_node", "remove_node", "modify_param", "rewire"]

    # Build prompts
    system_prompt = _build_mutation_system_prompt(allowed_nodes, allowed_patch_ops)
    user_prompt = _build_mutation_user_prompt(parent_graph, results_summary, num_children)

    # Call LLM
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    transcript_meta = {
        "run_id": run_id,
        "stage": "mutate",
        "artifact": parent_graph.graph_id,
        "suffix": f"{parent_graph.graph_id}_{timestamp}",
        "extra": {
            "parent_graph_id": parent_graph.graph_id,
            "num_children": num_children,
        },
    }

    if provider == "openai":
        llm_output = client_openai.complete_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            max_tokens=4000,
            transcript_meta=transcript_meta,
        )
    elif provider == "anthropic":
        llm_output = client_anthropic.complete_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            max_tokens=4000,
            transcript_meta=transcript_meta,
        )
    else:
        raise ValueError(f"Unknown provider: {provider}")

    # Parse patches
    patches = []
    for i, patch_data in enumerate(llm_output.get('patches', [])):
        patch = PatchSet(**patch_data)
        patches.append(patch)

    if len(patches) != num_children:
        raise ValueError(f"Expected {num_children} patches, got {len(patches)}")

    return patches


def _build_mutation_system_prompt(allowed_nodes: List[str], allowed_ops: List[str]) -> str:
    """Build system prompt for mutation."""
    registry = get_registry()

    # Build node docs (compact)
    node_summary = []
    for node_type in allowed_nodes:
        spec = registry.get(node_type)
        if spec:
            params = [f"{p.name}:{p.type.__name__}" for p in spec.params]
            node_summary.append(f"  {node_type}: {spec.description} ({', '.join(params) if params else 'no params'})")

    nodes_doc = "\n".join(node_summary)

    return f"""You are a quantitative strategy mutation expert.

Generate mutation patches to improve a parent strategy based on validation results.

MUTATION BUDGET (enforced strictly):
- Max 3 ops per patch
- Max +5 nodes per generation (total across all patches)
- Prefer small, targeted changes over large rewrites

ALLOWED OPERATIONS:
{', '.join(allowed_ops)}

ALLOWED NODE TYPES:
{nodes_doc}

MUTATION STRATEGIES:
- If high fragility → adjust parameters (±20%)
- If concentrated returns → add diversity (more conditions/exits)
- If performance cliff → add adaptive risk management
- If low Sharpe → tighten stops or widen targets
- DO NOT modify universe, time_config, or date_range

OUTPUT FORMAT:
{{"patches": [{{"patch_id": "...", "parent_graph_id": "...", "description": "...", "ops": [...]}}]}}

Each PatchOp must have:
- op_type: "add_node" | "remove_node" | "modify_param" | "rewire"
- node_id: target node ID
- Additional fields based on op_type

Output JSON only."""


def _build_mutation_user_prompt(
    parent_graph: StrategyGraph,
    results_summary: Dict[str, Any],
    num_children: int,
) -> str:
    """Build user prompt with parent graph and results."""
    parent_json = parent_graph.model_dump_json(indent=2)
    summary_json = json.dumps(results_summary, indent=2)

    return f"""Generate {num_children} mutation patches for this parent strategy.

PARENT GRAPH:
{parent_json}

VALIDATION RESULTS:
{summary_json}

OBJECTIVES:
- Address failure labels and penalties
- Improve fitness (current: {results_summary.get('fitness', 0):.3f})
- Maintain train performance, improve holdout
- Reduce fragility and concentration

Generate {num_children} diverse patches exploring different mutation directions.

Output JSON with "patches" array of {num_children} PatchSet objects."""
