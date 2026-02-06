"""Deterministic graph execution engine.

Executes StrategyGraph nodes in topological order with strict no-lookahead guarantees.
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, Tuple, List
from collections import defaultdict, deque

from graph.schema import StrategyGraph, Node
from graph.gene_pool import get_registry, NodeType


class GraphExecutionError(Exception):
    """Raised when graph execution fails."""
    pass


class GraphExecutor:
    """Executes strategy graphs deterministically on OHLCV data."""

    def __init__(self):
        self.registry = get_registry()

    def execute(self, graph: StrategyGraph, data: pd.DataFrame) -> Dict[Tuple[str, str], Any]:
        """Execute a strategy graph on OHLCV data.

        Args:
            graph: StrategyGraph to execute
            data: DataFrame with columns: timestamp, open, high, low, close, volume

        Returns:
            Context dict mapping (node_id, output_key) -> result

        Raises:
            GraphExecutionError: If graph is invalid or execution fails
        """
        # Validate graph structure
        self._validate_graph(graph)

        # Topologically sort nodes
        sorted_nodes = self._topological_sort(graph)

        # Execute nodes in order
        context = {}
        for node in sorted_nodes:
            try:
                node_outputs = self._execute_node(node, context, data)
                for output_key, output_value in node_outputs.items():
                    context[(node.id, output_key)] = output_value
            except Exception as e:
                raise GraphExecutionError(
                    f"Error executing node {node.id} (type={node.type}): {e}"
                ) from e

        return context

    def _validate_graph(self, graph: StrategyGraph):
        """Validate graph structure and node types."""
        # Use built-in validation
        graph.validate_structure()

        # Validate all node types exist in registry
        for node in graph.nodes:
            self._normalize_node_type(node)
            spec = self.registry.get(node.type)
            if not spec:
                raise GraphExecutionError(f"Unknown node type: {node.type}")

            # Validate required inputs are present
            for input_spec in spec.inputs:
                if input_spec.required and input_spec.name not in node.inputs:
                    raise GraphExecutionError(
                        f"Node {node.id} missing required input: {input_spec.name}"
                    )

    def _topological_sort(self, graph: StrategyGraph) -> List[Node]:
        """Topologically sort nodes by dependencies."""
        # Build adjacency list and in-degree count
        node_map = {n.id: n for n in graph.nodes}
        in_degree = {n.id: 0 for n in graph.nodes}
        adj_list = defaultdict(list)

        for node in graph.nodes:
            for ref_node_id, _ in node.inputs.values():
                adj_list[ref_node_id].append(node.id)
                in_degree[node.id] += 1

        # Kahn's algorithm
        queue = deque([node_id for node_id, degree in in_degree.items() if degree == 0])
        sorted_ids = []

        while queue:
            node_id = queue.popleft()
            sorted_ids.append(node_id)

            for neighbor_id in adj_list[node_id]:
                in_degree[neighbor_id] -= 1
                if in_degree[neighbor_id] == 0:
                    queue.append(neighbor_id)

        if len(sorted_ids) != len(graph.nodes):
            raise GraphExecutionError("Graph contains cycles")

        return [node_map[node_id] for node_id in sorted_ids]

    def _execute_node(
        self, node: Node, context: Dict[Tuple[str, str], Any], data: pd.DataFrame
    ) -> Dict[str, Any]:
        """Execute a single node.

        Args:
            node: Node to execute
            context: Current execution context
            data: OHLCV data

        Returns:
            Dict mapping output_key -> value
        """
        # Resolve inputs
        inputs = {}
        for input_key, (ref_node_id, ref_output_key) in node.inputs.items():
            context_key = (ref_node_id, ref_output_key)
            if context_key not in context:
                raise GraphExecutionError(
                    f"Node {node.id} references unavailable output: {ref_node_id}.{ref_output_key}"
                )
            inputs[input_key] = context[context_key]

        # Execute based on node type
        node_type = node.type
        params = node.params

        if node_type == NodeType.MARKET_DATA:
            return self._eval_market_data(data)
        elif node_type == NodeType.SMA:
            return self._eval_sma(inputs, params)
        elif node_type == NodeType.EMA:
            return self._eval_ema(inputs, params)
        elif node_type == NodeType.RSI:
            return self._eval_rsi(inputs, params)
        elif node_type == NodeType.ATR:
            return self._eval_atr(inputs, params)
        elif node_type == NodeType.RETURNS:
            return self._eval_returns(inputs, params)
        elif node_type == NodeType.ZSCORE:
            return self._eval_zscore(inputs, params)
        elif node_type == NodeType.BBANDS:
            return self._eval_bbands(inputs, params)
        elif node_type == NodeType.MACD:
            return self._eval_macd(inputs, params)
        elif node_type == NodeType.CONSTANT:
            return self._eval_constant(params)
        elif node_type == NodeType.COMPARE:
            return self._eval_compare(inputs, params)
        elif node_type == NodeType.AND:
            return self._eval_and(inputs)
        elif node_type == NodeType.OR:
            return self._eval_or(inputs)
        elif node_type == NodeType.NOT:
            return self._eval_not(inputs)
        elif node_type == NodeType.ENTRY_SIGNAL:
            return self._eval_entry_signal(inputs)
        elif node_type == NodeType.EXIT_SIGNAL:
            return self._eval_exit_signal(inputs)
        elif node_type == NodeType.STOP_LOSS_FIXED:
            return self._eval_stop_loss_fixed(params)
        elif node_type == NodeType.STOP_LOSS_ATR:
            return self._eval_stop_loss_atr(inputs, params)
        elif node_type == NodeType.TAKE_PROFIT_FIXED:
            return self._eval_take_profit_fixed(params)
        elif node_type == NodeType.TAKE_PROFIT_ATR:
            return self._eval_take_profit_atr(inputs, params)
        elif node_type == NodeType.POSITION_SIZING_FIXED:
            return self._eval_position_sizing_fixed(params)
        elif node_type == NodeType.POSITION_SIZING_PCT:
            return self._eval_position_sizing_pct(params)
        elif node_type == NodeType.BRACKET_ORDER:
            return self._eval_bracket_order(inputs)
        elif node_type == NodeType.RISK_MANAGER_DAILY:
            return self._eval_risk_manager_daily(inputs, params)
        else:
            raise GraphExecutionError(f"No evaluator for node type: {node_type}")

    def _normalize_node_type(self, node: Node):
        """Normalize node.type to canonical NodeType value."""
        if node.type in NodeType._value2member_map_:
            return
        upper = node.type.upper()
        if upper in NodeType.__members__:
            node.type = NodeType[upper].value

    # ===== NODE EVALUATORS =====

    def _eval_market_data(self, data: pd.DataFrame) -> Dict[str, pd.Series]:
        """MarketData node: returns OHLCV series.

        Handles timestamp as either column or index (for Phase 3 compatibility).
        """
        # Handle timestamp as either column or index
        if 'timestamp' in data.columns:
            timestamp = data["timestamp"]
        elif data.index.name == 'timestamp':
            # Phase 3 passes data with timestamp as index - convert to series
            timestamp = pd.Series(data.index, index=data.index, name='timestamp')
        else:
            raise ValueError(
                f"No 'timestamp' found in data. Columns: {data.columns.tolist()}, "
                f"Index name: {data.index.name}"
            )

        return {
            "open": data["open"],
            "high": data["high"],
            "low": data["low"],
            "close": data["close"],
            "volume": data["volume"],
            "timestamp": timestamp,
        }

    def _eval_constant(self, params: Dict) -> Dict[str, float]:
        """Constant node: returns scalar value."""
        return {"value": params["value"]}

    def _eval_sma(self, inputs: Dict, params: Dict) -> Dict[str, pd.Series]:
        """SMA node: simple moving average."""
        series = inputs["series"]
        period = params["period"]
        sma = series.rolling(window=period, min_periods=period).mean()
        return {"sma": sma}

    def _eval_ema(self, inputs: Dict, params: Dict) -> Dict[str, pd.Series]:
        """EMA node: exponential moving average."""
        series = inputs["series"]
        period = params["period"]
        ema = series.ewm(span=period, adjust=False, min_periods=period).mean()
        return {"ema": ema}

    def _eval_rsi(self, inputs: Dict, params: Dict) -> Dict[str, pd.Series]:
        """RSI node: relative strength index."""
        series = inputs["series"]
        period = params.get("period", 14)

        # Calculate price changes
        delta = series.diff()

        # Separate gains and losses
        gains = delta.where(delta > 0, 0.0)
        losses = -delta.where(delta < 0, 0.0)

        # Calculate rolling averages
        avg_gains = gains.rolling(window=period, min_periods=period).mean()
        avg_losses = losses.rolling(window=period, min_periods=period).mean()

        # Calculate RS and RSI
        rs = avg_gains / avg_losses
        rsi = 100.0 - (100.0 / (1.0 + rs))

        return {"rsi": rsi}

    def _eval_atr(self, inputs: Dict, params: Dict) -> Dict[str, pd.Series]:
        """ATR node: average true range."""
        high = inputs["high"]
        low = inputs["low"]
        close = inputs["close"]
        period = params.get("period", 14)

        # Calculate true range
        h_l = high - low
        h_pc = (high - close.shift(1)).abs()
        l_pc = (low - close.shift(1)).abs()

        tr = pd.concat([h_l, h_pc, l_pc], axis=1).max(axis=1)

        # Calculate ATR
        atr = tr.rolling(window=period, min_periods=period).mean()

        return {"atr": atr}

    def _eval_returns(self, inputs: Dict, params: Dict) -> Dict[str, pd.Series]:
        """Returns node: price returns."""
        series = inputs["series"]
        lookback = params.get("lookback", 1)
        returns = series.pct_change(periods=lookback)
        return {"returns": returns}

    def _eval_zscore(self, inputs: Dict, params: Dict) -> Dict[str, pd.Series]:
        """ZScore node: rolling z-score normalization."""
        series = inputs["series"]
        window = params.get("window", 20)

        rolling_mean = series.rolling(window=window, min_periods=window).mean()
        rolling_std = series.rolling(window=window, min_periods=window).std()

        zscore = (series - rolling_mean) / rolling_std

        return {"zscore": zscore}

    def _eval_bbands(self, inputs: Dict, params: Dict) -> Dict[str, pd.Series]:
        """BBands node: Bollinger Bands."""
        series = inputs["series"]
        period = params.get("period", 20)
        std_dev = params.get("std_dev", 2.0)

        middle = series.rolling(window=period, min_periods=period).mean()
        std = series.rolling(window=period, min_periods=period).std()

        upper = middle + (std * std_dev)
        lower = middle - (std * std_dev)

        return {"upper": upper, "middle": middle, "lower": lower}

    def _eval_macd(self, inputs: Dict, params: Dict) -> Dict[str, pd.Series]:
        """MACD node: MACD indicator."""
        series = inputs["series"]
        fast = params.get("fast", 12)
        slow = params.get("slow", 26)
        signal = params.get("signal", 9)

        ema_fast = series.ewm(span=fast, adjust=False, min_periods=fast).mean()
        ema_slow = series.ewm(span=slow, adjust=False, min_periods=slow).mean()

        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False, min_periods=signal).mean()
        histogram = macd_line - signal_line

        return {"macd": macd_line, "signal": signal_line, "histogram": histogram}

    def _eval_compare(self, inputs: Dict, params: Dict) -> Dict[str, pd.Series]:
        """Compare node: comparison operations."""
        a = inputs["a"]
        b = inputs["b"]
        op = params["op"]

        if op == ">":
            result = a > b
        elif op == "<":
            result = a < b
        elif op == ">=":
            result = a >= b
        elif op == "<=":
            result = a <= b
        elif op == "==":
            result = a == b
        elif op == "cross_up":
            result = (a > b) & (a.shift(1) <= b.shift(1))
        elif op == "cross_down":
            result = (a < b) & (a.shift(1) >= b.shift(1))
        elif op == "between":
            c = inputs.get("c")
            if c is None:
                raise GraphExecutionError("Compare node with op='between' requires input 'c'")
            result = (a >= b) & (a <= c)
        else:
            raise GraphExecutionError(f"Unknown comparison operator: {op}")

        return {"result": result}

    def _eval_and(self, inputs: Dict) -> Dict[str, pd.Series]:
        """And node: logical AND."""
        result = inputs["a"] & inputs["b"]
        return {"result": result}

    def _eval_or(self, inputs: Dict) -> Dict[str, pd.Series]:
        """Or node: logical OR."""
        result = inputs["a"] | inputs["b"]
        return {"result": result}

    def _eval_not(self, inputs: Dict) -> Dict[str, pd.Series]:
        """Not node: logical NOT."""
        result = ~inputs["a"]
        return {"result": result}

    def _eval_entry_signal(self, inputs: Dict) -> Dict[str, pd.Series]:
        """EntrySignal node: pass through entry condition."""
        return {"signal": inputs["condition"]}

    def _eval_exit_signal(self, inputs: Dict) -> Dict[str, pd.Series]:
        """ExitSignal node: pass through exit condition."""
        return {"signal": inputs["condition"]}

    def _eval_stop_loss_fixed(self, params: Dict) -> Dict[str, Dict]:
        """StopLossFixed node: fixed point stop loss config."""
        return {"stop_config": {"type": "fixed", "points": params["points"]}}

    def _eval_stop_loss_atr(self, inputs: Dict, params: Dict) -> Dict[str, Dict]:
        """StopLossATR node: ATR-based stop loss config."""
        return {
            "stop_config": {
                "type": "atr",
                "mult": params.get("mult", 1.0),
                "atr": inputs["atr"],
            }
        }

    def _eval_take_profit_fixed(self, params: Dict) -> Dict[str, Dict]:
        """TakeProfitFixed node: fixed point take profit config."""
        return {"tp_config": {"type": "fixed", "points": params["points"]}}

    def _eval_take_profit_atr(self, inputs: Dict, params: Dict) -> Dict[str, Dict]:
        """TakeProfitATR node: ATR-based take profit config."""
        return {
            "tp_config": {
                "type": "atr",
                "mult": params.get("mult", 2.0),
                "atr": inputs["atr"],
            }
        }

    def _eval_position_sizing_fixed(self, params: Dict) -> Dict[str, Dict]:
        """PositionSizingFixed node: fixed dollar position sizing."""
        return {"size_config": {"type": "fixed", "dollars": params.get("dollars", 10000.0)}}

    def _eval_position_sizing_pct(self, params: Dict) -> Dict[str, Dict]:
        """PositionSizingPct node: percentage of equity position sizing."""
        return {"size_config": {"type": "pct", "pct": params.get("pct", 0.10)}}

    def _eval_bracket_order(self, inputs: Dict) -> Dict[str, Dict]:
        """BracketOrder node: combine entry/exit/stop/tp/size into order config."""
        return {
            "orders": {
                "entry_signal": inputs["entry_signal"],
                "exit_signal": inputs.get("exit_signal"),
                "stop_config": inputs["stop_config"],
                "tp_config": inputs["tp_config"],
                "size_config": inputs["size_config"],
            }
        }

    def _eval_risk_manager_daily(self, inputs: Dict, params: Dict) -> Dict[str, Dict]:
        """RiskManagerDaily node: add daily risk limits to orders."""
        orders = inputs["orders"].copy()
        orders["risk_limits"] = {
            "max_loss_pct": params.get("max_loss_pct", 0.02),
            "max_profit_pct": params.get("max_profit_pct", 0.10),
            "max_trades": params.get("max_trades", 10),
        }
        return {"filtered_orders": orders}
