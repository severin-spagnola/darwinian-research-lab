"""Test that text comparison operators get normalized to symbols."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from graph.schema import StrategyGraph, Node, UniverseSpec, TimeConfig, DateRange
from llm.compile import _normalize_comparison_operators
from graph.gene_pool import NodeType


def test_comparison_operator_normalization():
    """Test that 'lt', 'gt', etc. get normalized to '<', '>', etc."""

    # Create a strategy with text operators
    strategy = StrategyGraph(
        graph_id="test_001",
        name="Test Strategy",
        nodes=[
            Node(
                id="market",
                type="MarketData",
                params={},
                inputs={}
            ),
            Node(
                id="const_30",
                type="Constant",
                params={"value": 30.0},
                inputs={}
            ),
            Node(
                id="compare_lt",
                type="Compare",
                params={"op": "lt"},  # Text format
                inputs={"a": ("market", "close"), "b": ("const_30", "value")}
            ),
            Node(
                id="compare_gt",
                type="Compare",
                params={"op": "greater_than"},  # Another text format
                inputs={"a": ("market", "close"), "b": ("const_30", "value")}
            ),
            Node(
                id="compare_already_ok",
                type="Compare",
                params={"op": "<"},  # Already correct
                inputs={"a": ("market", "close"), "b": ("const_30", "value")}
            ),
        ],
        outputs={"signal": ("compare_lt", "result")},
        universe=UniverseSpec(type="explicit", symbols=["AAPL"]),
        time=TimeConfig(
            timeframe="5m",
            date_range=DateRange(start="2024-01-01", end="2024-12-31")
        ),
    )

    # Apply normalization
    _normalize_comparison_operators(strategy)

    # Verify operators are normalized
    assert strategy.nodes[2].params["op"] == "<", f"Expected '<', got '{strategy.nodes[2].params['op']}'"
    assert strategy.nodes[3].params["op"] == ">", f"Expected '>', got '{strategy.nodes[3].params['op']}'"
    assert strategy.nodes[4].params["op"] == "<", f"Expected '<', got '{strategy.nodes[4].params['op']}'"

    print("Comparison operator normalization test passed.")


if __name__ == "__main__":
    test_comparison_operator_normalization()
