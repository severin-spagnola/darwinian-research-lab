"""Test that NodeType.X format in LLM output gets normalized correctly."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from graph.schema import StrategyGraph, Node, UniverseSpec, TimeConfig, DateRange
from llm.compile import _normalize_node_types
from graph.gene_pool import NodeType


def test_nodetype_enum_format_normalization():
    """Test that 'NodeType.MARKET_DATA' gets normalized to 'MarketData'."""

    # Create a strategy with NodeType.X format in node types
    strategy = StrategyGraph(
        graph_id="test_001",
        name="Test Strategy",
        nodes=[
            Node(
                id="market",
                type="NodeType.MARKET_DATA",  # This is what LLM might output
                params={},
                inputs={}
            ),
            Node(
                id="sma",
                type="NodeType.SMA",  # Another enum format
                params={"period": 20},
                inputs={"series": ("market", "close")}
            ),
            Node(
                id="const_50",
                type="Constant",
                params={"value": 50.0},
                inputs={}
            ),
            Node(
                id="compare",
                type="Compare",  # Already correct
                params={"op": "gt"},
                inputs={"a": ("sma", "output"), "b": ("const_50", "output")}
            ),
        ],
        outputs={"signal": ("compare", "output")},
        universe=UniverseSpec(type="explicit", symbols=["AAPL"]),
        time=TimeConfig(
            timeframe="5m",
            date_range=DateRange(start="2024-01-01", end="2024-12-31")
        ),
    )

    # Apply normalization
    _normalize_node_types(strategy)

    # Verify node types are normalized
    assert strategy.nodes[0].type == "MarketData", f"Expected 'MarketData', got '{strategy.nodes[0].type}'"
    assert strategy.nodes[1].type == "SMA", f"Expected 'SMA', got '{strategy.nodes[1].type}'"
    assert strategy.nodes[2].type == "Constant", f"Expected 'Constant', got '{strategy.nodes[2].type}'"
    assert strategy.nodes[3].type == "Compare", f"Expected 'Compare', got '{strategy.nodes[3].type}'"

    print("NodeType enum format normalization test passed.")


if __name__ == "__main__":
    test_nodetype_enum_format_normalization()
