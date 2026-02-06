"""Graph mutation patches for evolution.

Defines patch operations and application logic.
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Literal
from copy import deepcopy

from graph.schema import StrategyGraph, Node


class PatchOp(BaseModel):
    """Single patch operation."""
    op_type: Literal["add_node", "remove_node", "modify_param", "rewire"]
    node_id: str = ""  # Target node ID
    new_node: Dict[str, Any] = Field(default_factory=dict)  # For add_node
    param_name: str = ""  # For modify_param
    param_value: Any = None  # For modify_param
    input_name: str = ""  # For rewire
    new_source: List[str] = Field(default_factory=list)  # For rewire [node_id, output_key]


class PatchSet(BaseModel):
    """Set of patch operations to apply to a graph."""
    patch_id: str
    parent_graph_id: str
    description: str
    ops: List[PatchOp]

    def validate_ops(self):
        """Validate patch operations.

        Enforces:
        - Max 3 ops per patch
        - Max 5 nodes added (total across all ops)
        """
        if len(self.ops) > 3:
            raise ValueError("Max 3 ops per patch")

        # Count added nodes
        added_nodes = sum(1 for op in self.ops if op.op_type == "add_node")
        if added_nodes > 5:
            raise ValueError(f"Max 5 nodes can be added per patch, got {added_nodes}")

        return True


def apply_patch(graph: StrategyGraph, patch: PatchSet) -> StrategyGraph:
    """Apply patch to create child graph.

    Args:
        graph: Parent StrategyGraph
        patch: PatchSet with operations

    Returns:
        New StrategyGraph with patches applied

    Raises:
        ValueError: If patch is invalid
    """
    # Validate patch
    patch.validate_ops()

    # Deep copy graph
    child = deepcopy(graph)

    # Store original universe/time for validation
    original_universe = deepcopy(graph.universe)
    original_time = deepcopy(graph.time)

    # Update graph_id to reflect mutation
    child.graph_id = f"{graph.graph_id}_child_{patch.patch_id}"
    child.name = f"{graph.name} (mutated)"
    child.version = str(int(float(child.version or "1.0")) + 1)

    # Apply each operation
    for op in patch.ops:
        if op.op_type == "add_node":
            _add_node(child, op)
        elif op.op_type == "remove_node":
            _remove_node(child, op)
        elif op.op_type == "modify_param":
            _modify_param(child, op)
        elif op.op_type == "rewire":
            _rewire(child, op)
        else:
            raise ValueError(f"Unknown op_type: {op.op_type}")

    # Validate resulting graph
    child.validate_structure()

    # CRITICAL: Enforce universe/time/date_range immutability
    if child.universe != original_universe:
        raise ValueError("Patches cannot modify universe (locked)")
    if child.time != original_time:
        raise ValueError("Patches cannot modify time_config (locked)")

    return child


def _add_node(graph: StrategyGraph, op: PatchOp):
    """Add a node to the graph."""
    new_node = Node(**op.new_node)
    graph.nodes.append(new_node)


def _remove_node(graph: StrategyGraph, op: PatchOp):
    """Remove a node from the graph."""
    graph.nodes = [n for n in graph.nodes if n.id != op.node_id]

    # Remove references to this node from other nodes
    for node in graph.nodes:
        node.inputs = {
            k: v for k, v in node.inputs.items()
            if v[0] != op.node_id
        }


def _modify_param(graph: StrategyGraph, op: PatchOp):
    """Modify a node parameter."""
    for node in graph.nodes:
        if node.id == op.node_id:
            node.params[op.param_name] = op.param_value
            return

    raise ValueError(f"Node {op.node_id} not found")


def _rewire(graph: StrategyGraph, op: PatchOp):
    """Rewire a node input."""
    for node in graph.nodes:
        if node.id == op.node_id:
            node.inputs[op.input_name] = tuple(op.new_source)
            return

    raise ValueError(f"Node {op.node_id} not found")
