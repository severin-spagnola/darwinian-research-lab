"""Natural language to StrategyGraph compiler.

Compiles NL strategy descriptions into validated StrategyGraphs using LLM.
"""

import json
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

import config

from graph.schema import StrategyGraph, UniverseSpec, TimeConfig, Node
from graph.gene_pool import NodeType
from graph.gene_pool import get_registry
from llm import client_openai, client_anthropic
from llm.json_guard import validate_strategy_graph

logger = logging.getLogger(__name__)


def compile_nl_to_graph(
    nl_text: str,
    universe: UniverseSpec,
    time_config: TimeConfig,
    allowed_nodes: List[str] = None,
    provider: str = "openai",
    temperature: float = 0.7,
    run_id: Optional[str] = None,
) -> StrategyGraph:
    """Compile natural language to StrategyGraph.

    IMPORTANT: universe and time_config are LOCKED inputs.
    The LLM must embed these exact values in the compiled graph.

    Args:
        nl_text: Natural language strategy description
        universe: LOCKED universe specification (must not be modified)
        time_config: LOCKED timeframe/date configuration (must not be modified)
        allowed_nodes: List of allowed node types (default: all from registry)
        provider: "openai" or "anthropic"
        temperature: LLM temperature

    Returns:
        Validated StrategyGraph with locked universe/time_config

    Raises:
        ValidationError: If LLM output is invalid
    """
    registry = get_registry()

    if allowed_nodes is None:
        allowed_nodes = registry.get_all_types()

    # Build node documentation
    node_docs = _build_node_docs(allowed_nodes)

    # Build prompts
    system_prompt = _build_system_prompt(node_docs)
    user_prompt = _build_user_prompt(nl_text, universe, time_config)

    # Call LLM
    transcript_meta = _build_transcript_meta(run_id, "compile_initial", artifact="adam")
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

    # Validate and parse
    strategy = validate_strategy_graph(llm_output, provider)

    _normalize_node_types(strategy)
    _normalize_numeric_inputs(strategy)
    _normalize_comparison_operators(strategy)

    # CRITICAL: Verify the produced graph structure is valid
    try:
        strategy.validate_structure()
    except ValueError as structure_error:
        logger.info("Strategy graph failed structure validation; attempting one repair")
        strategy = _attempt_structure_repair(
            llm_output=llm_output,
            nl_text=nl_text,
            universe=universe,
            time_config=time_config,
            error=structure_error,
            provider=provider,
            temperature=temperature,
            run_id=run_id,
            attempt=1,
        )

    # CRITICAL: Verify universe and time_config were not modified
    if strategy.universe != universe:
        raise ValueError("LLM modified universe (not allowed)")
    if strategy.time != time_config:
        raise ValueError("LLM modified time_config (not allowed)")

    return strategy


def _build_node_docs(allowed_nodes: List[str]) -> str:
    """Build documentation for allowed node types."""
    registry = get_registry()

    docs = []
    for node_type in allowed_nodes:
        spec = registry.get(node_type)
        if not spec:
            continue

        params_doc = ", ".join([f"{p.name}: {p.type.__name__}" for p in spec.params])
        inputs_doc = ", ".join([f"{i.name}: {i.type}" for i in spec.inputs])
        outputs_doc = ", ".join([f"{o.name}: {o.type}" for o in spec.outputs])

        # Special case: Document allowed operators for Compare node
        extra_info = ""
        if node_type == "Compare":
            extra_info = "\n  Allowed operators: <, >, <=, >=, ==, cross_up, cross_down, between"

        doc = f"""
{node_type}:
  Description: {spec.description}
  Params: {params_doc or 'none'}
  Inputs: {inputs_doc or 'none'}
  Outputs: {outputs_doc}{extra_info}
""".strip()
        docs.append(doc)

    return "\n\n".join(docs)


def _build_system_prompt(node_docs: str) -> str:
    """Build system prompt for compilation."""
    return f"""You are a quantitative trading strategy compiler.

Convert natural language strategy descriptions into StrategyGraph JSON.

RULES:
1. Use ONLY the allowed node types provided below
2. Create a directed acyclic graph (no cycles)
3. Each node must have: id, type, params, inputs
4. Node IDs must be unique and descriptive (e.g., "sma_fast", "entry_signal")
5. Connect nodes via inputs: {{"input_name": ["source_node_id", "output_name"]}}
6. Include entry/exit signals, stops, targets, position sizing
7. Final output must reference the last risk manager or order node
8. DO NOT modify universe, time_config, or date_range (these are locked)
9. If you need to pass a number, create a Constant node and refer to it; do not reference raw number IDs (like "30") directly.
10. Use the "Constant" node as spelled above; do not use uppercase aliases like "CONSTANT"
11. For Compare nodes, use symbol operators: "<", ">", "<=", ">=", "==", "!=", "cross_up", "cross_down", "between" (not text like "lt" or "gt")

ALLOWED NODE TYPES:
{node_docs}

OUTPUT FORMAT:
Return ONLY valid JSON matching StrategyGraph schema.
No explanations, just JSON."""


def _build_user_prompt(
    nl_text: str,
    universe: UniverseSpec,
    time_config: TimeConfig,
) -> str:
    """Build user prompt with locked parameters."""
    universe_json = universe.model_dump_json(indent=2)
    time_json = time_config.model_dump_json(indent=2)

    return f"""Compile this strategy to StrategyGraph JSON:

STRATEGY:
{nl_text}

LOCKED PARAMETERS (do not modify):

Universe:
{universe_json}

Time Config:
{time_json}

Generate the complete StrategyGraph JSON with:
- graph_id: unique ID (lowercase, underscores)
- name: descriptive name
- version: "1.0"
- nodes: list of Node objects
- outputs: {{"orders": ["final_node_id", "output_name"]}}
- metadata: {{"description": "...", "author": "llm"}}
- universe: USE EXACT VALUE ABOVE
- time: USE EXACT VALUE ABOVE
- When referencing numeric constants, add a Constant node (e.g., id "const_30") and point Compare inputs there; do not use raw numbers as node IDs.

Output JSON only."""


def _build_transcript_meta(
    run_id: Optional[str],
    stage: str,
    artifact: Optional[str] = None,
    suffix: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build metadata for transcript recording."""
    meta = {"run_id": run_id, "stage": stage}
    if artifact:
        meta["artifact"] = artifact
    if suffix:
        meta["suffix"] = suffix
    if extra:
        meta["extra"] = extra
    return meta


def _attempt_structure_repair(
    llm_output: Dict[str, Any],
    nl_text: str,
    universe: UniverseSpec,
    time_config: TimeConfig,
    error: ValueError,
    provider: str,
    temperature: float,
    run_id: Optional[str],
    attempt: int = 1,
) -> StrategyGraph:
    """Try once to repair structural issues discovered after parsing."""
    system_prompt = "You output StrategyGraph JSON only."

    user_prompt = f"""Original natural language prompt:
{nl_text}

Generated StrategyGraph JSON:
{json.dumps(llm_output, indent=2)}

Validation error:
{str(error)}

Return corrected full StrategyGraph JSON with all referenced node IDs present.
Do not change universe, time_config, or date_range."""

    transcript_meta = _build_transcript_meta(
        run_id,
        "compile_repair",
        artifact="adam",
        suffix=f"attempt{attempt}",
        extra={"validation_error": str(error)},
    )
    if provider == "openai":
        repaired_json = client_openai.complete_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.0,
            max_tokens=4000,
            transcript_meta=transcript_meta,
        )
    elif provider == "anthropic":
        repaired_json = client_anthropic.complete_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.0,
            max_tokens=4000,
            transcript_meta=transcript_meta,
        )
    else:
        raise ValueError(f"Unknown provider: {provider}")

    repaired_strategy = validate_strategy_graph(repaired_json, provider)
    _normalize_node_types(repaired_strategy)
    _normalize_numeric_inputs(repaired_strategy)
    _normalize_comparison_operators(repaired_strategy)
    try:
        repaired_strategy.validate_structure()
        return repaired_strategy
    except ValueError as repair_error:
        logger.error("Structure repair attempt failed; saving artifacts if possible")
        if run_id:
            _save_failed_compile(
                run_id=run_id,
                original_graph=llm_output,
                repair_attempt=repaired_json,
                original_error=str(error),
                repair_error=str(repair_error),
            )
        raise ValueError(f"Structure validation failed after repair attempt: {repair_error}")


def _save_failed_compile(
    run_id: str,
    original_graph: Dict[str, Any],
    repair_attempt: Dict[str, Any],
    original_error: str,
    repair_error: str,
):
    """Persist the broken and attempted graph JSON for offline investigation."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_graphs_dir = config.RESULTS_DIR / "runs" / run_id / "graphs"
    run_graphs_dir.mkdir(parents=True, exist_ok=True)
    filename = run_graphs_dir / f"failed_compile_{timestamp}.json"
    payload = {
        "timestamp": timestamp,
        "original_error": original_error,
        "repair_error": repair_error,
        "original_graph": original_graph,
        "repair_attempt": repair_attempt,
    }
    with open(filename, "w") as f:
        json.dump(payload, f, indent=2)
    logger.info(f"Saved failed compile artifacts to {filename}")

    failure_dir = config.RESULTS_DIR / "runs" / run_id / "compile_failures"
    failure_dir.mkdir(parents=True, exist_ok=True)

    raw_file = failure_dir / f"{timestamp}_raw.json"
    with open(raw_file, "w") as f:
        json.dump(original_graph, f, indent=2)

    error_file = failure_dir / f"{timestamp}_error.txt"
    with open(error_file, "w") as f:
        f.write(f"Original error:\n{original_error}\n\nRepair error:\n{repair_error}\n")


def _normalize_node_types(strategy: StrategyGraph):
    """Ensure node.type matches the canonical registry values."""
    normalized = False
    for node in strategy.nodes:
        if node.type in NodeType._value2member_map_:
            continue

        # Handle "NodeType.MARKET_DATA" format
        if node.type.startswith("NodeType."):
            enum_name = node.type.split(".", 1)[1]
            if enum_name in NodeType.__members__:
                node.type = NodeType[enum_name].value
                normalized = True
                continue

        # Handle uppercase/case variations
        upper = node.type.upper()
        if upper in NodeType.__members__:
            node.type = NodeType[upper].value
            normalized = True
    if normalized:
        logger.debug("Normalized node type casing to registry values.")


def _normalize_numeric_inputs(strategy: StrategyGraph):
    """Replace numeric literals in node inputs with Constant nodes."""
    value_map: Dict[float, str] = {}
    existing_ids = {node.id for node in strategy.nodes}
    for node in list(strategy.nodes):
        if node.type == NodeType.CONSTANT.value:
            try:
                value = float(node.params.get("value", 0.0))
            except Exception:
                continue
            value_map[value] = node.id

    new_nodes: List[Node] = []

    for node in list(strategy.nodes):
        updated_inputs = {}
        for input_key, (ref_id, output_key) in node.inputs.items():
            if _is_number_literal(ref_id):
                value = float(ref_id)
                const_id = value_map.get(value)
                if not const_id:
                    candidate = f"const_{str(value).replace('.', '_').replace('-', 'neg')}"
                    suffix = 1
                    while candidate in existing_ids:
                        candidate = f"const_{suffix}_{str(value).replace('.', '_')}"
                        suffix += 1
                    const_node = Node(
                        id=candidate,
                        type=NodeType.CONSTANT.value,
                        params={"value": value},
                        inputs={},
                    )
                    new_nodes.append(const_node)
                    existing_ids.add(candidate)
                    const_id = candidate
                    value_map[value] = const_id
                updated_inputs[input_key] = (const_id, "value")
            else:
                updated_inputs[input_key] = (ref_id, output_key)
        node.inputs = updated_inputs

    if new_nodes:
        strategy.nodes.extend(new_nodes)
        logger.debug("Inserted Constant nodes for numeric literals.")


def _normalize_comparison_operators(strategy: StrategyGraph):
    """Normalize comparison operators from text format to symbols.

    LLMs often output 'lt', 'gt', 'eq', etc. but the Compare node expects '<', '>', '==', etc.
    """
    # Mapping from text operators to symbols
    OPERATOR_MAP = {
        'lt': '<',
        'gt': '>',
        'le': '<=',
        'ge': '>=',
        'eq': '==',
        'ne': '!=',
        'lte': '<=',
        'gte': '>=',
        'less_than': '<',
        'greater_than': '>',
        'less_than_or_equal': '<=',
        'greater_than_or_equal': '>=',
        'equal': '==',
        'not_equal': '!=',
    }

    normalized = False
    for node in strategy.nodes:
        if node.type == NodeType.COMPARE.value and 'op' in node.params:
            op = node.params['op']
            if op in OPERATOR_MAP:
                node.params['op'] = OPERATOR_MAP[op]
                normalized = True

    if normalized:
        logger.debug("Normalized comparison operators to symbol format.")


def _is_number_literal(ref: Any) -> bool:
    """Return True if the reference is a numeric literal."""
    if isinstance(ref, (int, float)):
        return True
    if isinstance(ref, str):
        try:
            float(ref)
            return True
        except ValueError:
            return False
    return False
