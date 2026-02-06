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


def build_graph() -> StrategyGraph:
    universe = UniverseSpec(type="explicit", symbols=["AAPL"])
    time_config = TimeConfig(
        timeframe="5m",
        date_range=DateRange(start="2024-01-01", end="2024-01-07"),
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
            id="constant_30",
            type="Constant",
            params={"value": 30.0},
            inputs={},
        ),
        Node(
            id="rsi_lt_30",
            type="Compare",
            params={"op": "<"},
            inputs={
                "a": ("rsi", "rsi"),
                "b": ("constant_30", "value"),
            },
        ),
        Node(
            id="entry",
            type="EntrySignal",
            params={},
            inputs={"condition": ("rsi_lt_30", "result")},
        ),
    ]

    return StrategyGraph(
        graph_id="test_constant_compare",
        name="Test Constant Compare",
        universe=universe,
        time=time_config,
        constraints=ExecutionConstraints(),
        nodes=nodes,
        outputs={"entry_signal": ("entry", "signal")},
        metadata={"description": "unit test constant"},  # type: ignore[arg-type]
    )


def make_data() -> pd.DataFrame:
    index = pd.date_range("2024-01-01", periods=5, freq="5min", tz="UTC")
    return pd.DataFrame(
        {
            "timestamp": index,
            "open": [100, 101, 99, 98, 97],
            "high": [101, 102, 100, 99, 98],
            "low": [99, 100, 98, 97, 96],
            "close": [100, 100.5, 99.5, 98.5, 97.5],
            "volume": [1000, 1100, 1050, 1200, 1300],
        }
    )


def main():
    graph = build_graph()
    graph.validate_structure()

    executor = GraphExecutor()
    data = make_data()
    context = executor.execute(graph, data)

    # Ensure entry signal exists and is boolean
    signal = context[("entry", "signal")]
    assert signal.dtype == bool or signal.dtype == "bool"
    print("Constant node execution test passed.")


if __name__ == "__main__":
    main()
