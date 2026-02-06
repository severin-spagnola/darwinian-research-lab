import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from graph.executor import GraphExecutor
from graph.schema import (
    StrategyGraph,
    Node,
    UniverseSpec,
    TimeConfig,
    DateRange,
    ExecutionConstraints,
)
from llm.compile import _normalize_numeric_inputs


def build_graph_with_literal() -> StrategyGraph:
    universe = UniverseSpec(type="explicit", symbols=["AAPL"])
    time_config = TimeConfig(
        timeframe="5m",
        date_range=DateRange(start="2024-01-01", end="2024-01-02"),
    )
    nodes = [
        Node(id="market_data", type="MarketData", params={}, inputs={}),
        Node(
            id="rsi",
            type="RSI",
            params={"period": 3},
            inputs={"series": ("market_data", "close")},
        ),
        Node(
            id="entry_compare",
            type="Compare",
            params={"op": "<"},
            inputs={
                "a": ("rsi", "rsi"),
                "b": ("30", "value"),  # literal numeric reference should normalize
            },
        ),
        Node(
            id="entry",
            type="EntrySignal",
            params={},
            inputs={"condition": ("entry_compare", "result")},
        ),
    ]
    return StrategyGraph(
        graph_id="literal_test",
        name="Literal Normalize Test",
        universe=universe,
        time=time_config,
        constraints=ExecutionConstraints(),
        nodes=nodes,
        outputs={"entry": ("entry", "signal")},
    )


def make_data() -> pd.DataFrame:
    index = pd.date_range("2024-01-01", periods=3, freq="5min", tz="UTC")
    return pd.DataFrame(
        {
            "timestamp": index,
            "open": [100, 101, 102],
            "high": [101, 102, 103],
            "low": [99, 100, 101],
            "close": [100, 101, 100],
            "volume": [1000, 1100, 1200],
        }
    )


def main():
    graph = build_graph_with_literal()
    _normalize_numeric_inputs(graph)
    graph.validate_structure()

    executor = GraphExecutor()
    context = executor.execute(graph, make_data())
    signal = context[("entry", "signal")]
    assert signal.dtype == bool or signal.dtype == "bool"
    print("Literal normalization test passed.")


if __name__ == "__main__":
    main()
