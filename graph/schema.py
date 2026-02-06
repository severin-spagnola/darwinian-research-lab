from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any, Tuple, Union
from datetime import datetime


class UniverseSpec(BaseModel):
    """Specification of which symbols to trade."""
    type: str  # "explicit", "sp500", "nasdaq100", "top_market_cap"
    symbols: Optional[List[str]] = None  # For explicit type
    count: Optional[int] = None  # For top_market_cap
    
    def resolve_symbols(self) -> List[str]:
        """Resolve universe to actual symbol list."""
        if self.type == "explicit":
            return self.symbols or []
        elif self.type == "sp500":
            from config import STATIC_DIR
            sp500_file = STATIC_DIR / "sp500.txt"
            if sp500_file.exists():
                return sp500_file.read_text().strip().split('\n')
            return []
        elif self.type == "nasdaq100":
            from config import STATIC_DIR
            nasdaq_file = STATIC_DIR / "nasdaq100.txt"
            if nasdaq_file.exists():
                return nasdaq_file.read_text().strip().split('\n')
            return []
        elif self.type == "top_market_cap":
            # TODO: Implement market cap sorting
            raise NotImplementedError("top_market_cap not yet implemented")
        else:
            raise ValueError(f"Unknown universe type: {self.type}")


class TimeframeSpec(BaseModel):
    """Specification of timeframe(s) to evaluate."""
    type: str  # "single" or "sweep"
    timeframes: List[str]  # e.g., ["5m"] or ["1m", "2m", "5m", "15m", "30m", "1h"]


class DateRange(BaseModel):
    start: str  # YYYY-MM-DD
    end: str  # YYYY-MM-DD


class TimeConfig(BaseModel):
    timeframe: str
    session_tz: Optional[str] = "America/New_York"
    date_range: DateRange


class ExecutionConstraints(BaseModel):
    execution: str = "next_bar_open"
    no_lookahead: bool = True
    max_nodes: int = 40


class Node(BaseModel):
    """A single node in the strategy graph."""
    id: str
    type: str  # Must be in gene pool registry
    params: Dict[str, Any] = Field(default_factory=dict)
    inputs: Dict[str, Tuple[str, str]] = Field(default_factory=dict)  # input_key -> (node_id, output_key)
    
    def get_input_ref(self, input_key: str) -> Optional[Tuple[str, str]]:
        """Get the (node_id, output_key) that feeds this input."""
        return self.inputs.get(input_key)


class StrategyGraph(BaseModel):
    """Complete strategy specification as a directed graph."""
    graph_id: str
    name: str
    version: str = "1.0"
    
    universe: UniverseSpec
    time: TimeConfig
    constraints: ExecutionConstraints = Field(default_factory=ExecutionConstraints)
    
    nodes: List[Node]
    outputs: Dict[str, Tuple[str, str]]  # output_name -> (node_id, output_key)
    
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    def get_node(self, node_id: str) -> Optional[Node]:
        """Get a node by ID."""
        for node in self.nodes:
            if node.id == node_id:
                return node
        return None
    
    def validate_structure(self):
        """Validate graph structure (no cycles, valid references, etc.)."""
        # Check unique node IDs
        node_ids = [n.id for n in self.nodes]
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("Duplicate node IDs found")
        
        # Check all input references are valid
        for node in self.nodes:
            for input_key, (ref_node_id, ref_output_key) in node.inputs.items():
                if ref_node_id not in node_ids:
                    raise ValueError(f"Node {node.id} references non-existent node {ref_node_id}")
        
        # Check output references are valid
        for output_name, (node_id, output_key) in self.outputs.items():
            if node_id not in node_ids:
                raise ValueError(f"Output {output_name} references non-existent node {node_id}")
        
        # Check for cycles using DFS
        from collections import defaultdict
        
        graph = defaultdict(list)
        for node in self.nodes:
            for ref_node_id, _ in node.inputs.values():
                graph[ref_node_id].append(node.id)
        
        def has_cycle(node_id, visited, rec_stack):
            visited.add(node_id)
            rec_stack.add(node_id)
            
            for neighbor in graph[node_id]:
                if neighbor not in visited:
                    if has_cycle(neighbor, visited, rec_stack):
                        return True
                elif neighbor in rec_stack:
                    return True
            
            rec_stack.remove(node_id)
            return False
        
        visited = set()
        for node_id in node_ids:
            if node_id not in visited:
                if has_cycle(node_id, visited, set()):
                    raise ValueError("Graph contains cycles")