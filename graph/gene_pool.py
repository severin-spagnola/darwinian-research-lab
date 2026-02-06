# graph/gene_pool.py
from typing import Dict, List, Any, Callable, Optional
from dataclasses import dataclass
from enum import Enum


class NodeType(str, Enum):
    """Enum of all allowed node types."""
    # Data/Time
    MARKET_DATA = "MarketData"
    TIME_WINDOW_MASK = "TimeWindowMask"
    CONSTANT = "Constant"
    
    # Features
    SMA = "SMA"
    EMA = "EMA"
    RSI = "RSI"
    ATR = "ATR"
    RETURNS = "Returns"
    ZSCORE = "ZScore"
    BBANDS = "BBands"
    MACD = "MACD"
    
    # Logic
    COMPARE = "Compare"
    AND = "And"
    OR = "Or"
    NOT = "Not"
    
    # Signals
    ENTRY_SIGNAL = "EntrySignal"
    EXIT_SIGNAL = "ExitSignal"
    
    # Orders/Risk
    BRACKET_ORDER = "BracketOrder"
    STOP_LOSS_FIXED = "StopLossFixed"
    STOP_LOSS_ATR = "StopLossATR"
    TAKE_PROFIT_FIXED = "TakeProfitFixed"
    TAKE_PROFIT_ATR = "TakeProfitATR"
    POSITION_SIZING_FIXED = "PositionSizingFixed"
    POSITION_SIZING_PCT = "PositionSizingPct"
    RISK_MANAGER_DAILY = "RiskManagerDaily"


@dataclass
class ParamSpec:
    """Specification for a node parameter."""
    name: str
    type: type
    default: Any = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    options: Optional[List[Any]] = None
    mutable: bool = True  # Can this param be mutated in evolution?


@dataclass
class IOSpec:
    """Specification for input/output."""
    name: str
    type: str  # "Series[float]", "Series[bool]", "Scalar[float]", "Orders", etc.
    required: bool = True


@dataclass
class NodeSpec:
    """Complete specification for a node type."""
    type: str
    description: str
    params: List[ParamSpec]
    inputs: List[IOSpec]
    outputs: List[IOSpec]
    evaluator: Optional[Callable] = None  # Function to evaluate this node


class NodeRegistry:
    """Registry of all allowed node types (gene pool)."""
    
    def __init__(self):
        self.specs: Dict[str, NodeSpec] = {}
        self._register_all_nodes()
    
    def register(self, spec: NodeSpec):
        """Register a node type."""
        self.specs[spec.type] = spec
    
    def get(self, node_type: str) -> Optional[NodeSpec]:
        """Get spec for a node type."""
        return self.specs.get(node_type)
    
    def get_all_types(self) -> List[str]:
        """Get list of all registered node types."""
        return list(self.specs.keys())
    
    def validate_node(self, node_type: str, params: Dict[str, Any], inputs: Dict[str, Any]) -> bool:
        """Validate a node configuration."""
        spec = self.get(node_type)
        if not spec:
            return False
        
        # Check required params
        for param_spec in spec.params:
            if param_spec.default is None and param_spec.name not in params:
                return False
        
        # Check required inputs
        for input_spec in spec.inputs:
            if input_spec.required and input_spec.name not in inputs:
                return False
        
        return True
    
    def _register_all_nodes(self):
        """Register all MVP node types."""
        
        # ===== DATA/TIME =====
        self.register(NodeSpec(
            type=NodeType.MARKET_DATA,
            description="Provides OHLCV data series",
            params=[],
            inputs=[],
            outputs=[
                IOSpec("open", "Series[float]"),
                IOSpec("high", "Series[float]"),
                IOSpec("low", "Series[float]"),
                IOSpec("close", "Series[float]"),
                IOSpec("volume", "Series[float]"),
            IOSpec("timestamp", "Series[datetime]"),
        ]
        ))

        self.register(NodeSpec(
            type=NodeType.CONSTANT,
            description="Constant scalar value used for comparisons",
            params=[
                ParamSpec("value", float),
            ],
            inputs=[],
            outputs=[
                IOSpec("value", "Scalar[float]"),
            ],
        ))
        
        # ===== FEATURES =====
        self.register(NodeSpec(
            type=NodeType.SMA,
            description="Simple Moving Average",
            params=[
                ParamSpec("period", int, min_value=2, max_value=500)
            ],
            inputs=[
                IOSpec("series", "Series[float]")
            ],
            outputs=[
                IOSpec("sma", "Series[float]")
            ]
        ))
        
        self.register(NodeSpec(
            type=NodeType.EMA,
            description="Exponential Moving Average",
            params=[
                ParamSpec("period", int, min_value=2, max_value=500)
            ],
            inputs=[
                IOSpec("series", "Series[float]")
            ],
            outputs=[
                IOSpec("ema", "Series[float]")
            ]
        ))
        
        self.register(NodeSpec(
            type=NodeType.RSI,
            description="Relative Strength Index",
            params=[
                ParamSpec("period", int, default=14, min_value=2, max_value=100)
            ],
            inputs=[
                IOSpec("series", "Series[float]")
            ],
            outputs=[
                IOSpec("rsi", "Series[float]")
            ]
        ))
        
        self.register(NodeSpec(
            type=NodeType.ATR,
            description="Average True Range",
            params=[
                ParamSpec("period", int, default=14, min_value=2, max_value=100)
            ],
            inputs=[
                IOSpec("high", "Series[float]"),
                IOSpec("low", "Series[float]"),
                IOSpec("close", "Series[float]")
            ],
            outputs=[
                IOSpec("atr", "Series[float]")
            ]
        ))
        
        self.register(NodeSpec(
            type=NodeType.RETURNS,
            description="Price returns over lookback period",
            params=[
                ParamSpec("lookback", int, default=1, min_value=1, max_value=100)
            ],
            inputs=[
                IOSpec("series", "Series[float]")
            ],
            outputs=[
                IOSpec("returns", "Series[float]")
            ]
        ))
        
        self.register(NodeSpec(
            type=NodeType.ZSCORE,
            description="Z-score normalization over rolling window",
            params=[
                ParamSpec("window", int, default=20, min_value=2, max_value=500)
            ],
            inputs=[
                IOSpec("series", "Series[float]")
            ],
            outputs=[
                IOSpec("zscore", "Series[float]")
            ]
        ))
        
        self.register(NodeSpec(
            type=NodeType.BBANDS,
            description="Bollinger Bands",
            params=[
                ParamSpec("period", int, default=20, min_value=2, max_value=200),
                ParamSpec("std_dev", float, default=2.0, min_value=0.5, max_value=5.0)
            ],
            inputs=[
                IOSpec("series", "Series[float]")
            ],
            outputs=[
                IOSpec("upper", "Series[float]"),
                IOSpec("middle", "Series[float]"),
                IOSpec("lower", "Series[float]")
            ]
        ))
        
        self.register(NodeSpec(
            type=NodeType.MACD,
            description="MACD indicator",
            params=[
                ParamSpec("fast", int, default=12, min_value=2, max_value=100),
                ParamSpec("slow", int, default=26, min_value=2, max_value=200),
                ParamSpec("signal", int, default=9, min_value=2, max_value=50)
            ],
            inputs=[
                IOSpec("series", "Series[float]")
            ],
            outputs=[
                IOSpec("macd", "Series[float]"),
                IOSpec("signal", "Series[float]"),
                IOSpec("histogram", "Series[float]")
            ]
        ))
        
        # ===== LOGIC =====
        self.register(NodeSpec(
            type=NodeType.COMPARE,
            description="Comparison operator",
            params=[
                ParamSpec("op", str, options=[">", "<", ">=", "<=", "==", "cross_up", "cross_down", "between"])
            ],
            inputs=[
                IOSpec("a", "Series[float]"),
                IOSpec("b", "Series[float]"),
                IOSpec("c", "Series[float]", required=False)  # For 'between'
            ],
            outputs=[
                IOSpec("result", "Series[bool]")
            ]
        ))
        
        self.register(NodeSpec(
            type=NodeType.AND,
            description="Logical AND",
            params=[],
            inputs=[
                IOSpec("a", "Series[bool]"),
                IOSpec("b", "Series[bool]")
            ],
            outputs=[
                IOSpec("result", "Series[bool]")
            ]
        ))
        
        self.register(NodeSpec(
            type=NodeType.OR,
            description="Logical OR",
            params=[],
            inputs=[
                IOSpec("a", "Series[bool]"),
                IOSpec("b", "Series[bool]")
            ],
            outputs=[
                IOSpec("result", "Series[bool]")
            ]
        ))
        
        self.register(NodeSpec(
            type=NodeType.NOT,
            description="Logical NOT",
            params=[],
            inputs=[
                IOSpec("a", "Series[bool]")
            ],
            outputs=[
                IOSpec("result", "Series[bool]")
            ]
        ))
        
        # ===== SIGNALS =====
        self.register(NodeSpec(
            type=NodeType.ENTRY_SIGNAL,
            description="Entry signal generator",
            params=[],
            inputs=[
                IOSpec("condition", "Series[bool]")
            ],
            outputs=[
                IOSpec("signal", "Series[bool]")
            ]
        ))
        
        self.register(NodeSpec(
            type=NodeType.EXIT_SIGNAL,
            description="Exit signal generator",
            params=[],
            inputs=[
                IOSpec("condition", "Series[bool]")
            ],
            outputs=[
                IOSpec("signal", "Series[bool]")
            ]
        ))
        
        # ===== RISK/ORDERS =====
        self.register(NodeSpec(
            type=NodeType.STOP_LOSS_FIXED,
            description="Fixed point stop loss",
            params=[
                ParamSpec("points", float, min_value=0.01, max_value=1000.0)
            ],
            inputs=[],
            outputs=[
                IOSpec("stop_config", "StopConfig")
            ]
        ))
        
        self.register(NodeSpec(
            type=NodeType.STOP_LOSS_ATR,
            description="ATR-based stop loss",
            params=[
                ParamSpec("mult", float, default=1.0, min_value=0.1, max_value=10.0)
            ],
            inputs=[
                IOSpec("atr", "Series[float]")
            ],
            outputs=[
                IOSpec("stop_config", "StopConfig")
            ]
        ))
        
        self.register(NodeSpec(
            type=NodeType.TAKE_PROFIT_FIXED,
            description="Fixed point take profit",
            params=[
                ParamSpec("points", float, min_value=0.01, max_value=1000.0)
            ],
            inputs=[],
            outputs=[
                IOSpec("tp_config", "TPConfig")
            ]
        ))
        
        self.register(NodeSpec(
            type=NodeType.TAKE_PROFIT_ATR,
            description="ATR-based take profit",
            params=[
                ParamSpec("mult", float, default=2.0, min_value=0.1, max_value=20.0)
            ],
            inputs=[
                IOSpec("atr", "Series[float]")
            ],
            outputs=[
                IOSpec("tp_config", "TPConfig")
            ]
        ))
        
        self.register(NodeSpec(
            type=NodeType.POSITION_SIZING_FIXED,
            description="Fixed dollar position sizing",
            params=[
                ParamSpec("dollars", float, default=10000.0, min_value=100.0, max_value=1000000.0)
            ],
            inputs=[],
            outputs=[
                IOSpec("size_config", "SizeConfig")
            ]
        ))
        
        self.register(NodeSpec(
            type=NodeType.POSITION_SIZING_PCT,
            description="Percentage of equity position sizing",
            params=[
                ParamSpec("pct", float, default=0.10, min_value=0.01, max_value=1.0)
            ],
            inputs=[],
            outputs=[
                IOSpec("size_config", "SizeConfig")
            ]
        ))
        
        self.register(NodeSpec(
            type=NodeType.BRACKET_ORDER,
            description="Bracket order with entry/stop/target",
            params=[],
            inputs=[
                IOSpec("entry_signal", "Series[bool]"),
                IOSpec("exit_signal", "Series[bool]", required=False),
                IOSpec("stop_config", "StopConfig"),
                IOSpec("tp_config", "TPConfig"),
                IOSpec("size_config", "SizeConfig")
            ],
            outputs=[
                IOSpec("orders", "Orders")
            ]
        ))
        
        self.register(NodeSpec(
            type=NodeType.RISK_MANAGER_DAILY,
            description="Daily risk management rules",
            params=[
                ParamSpec("max_loss_pct", float, default=0.02, min_value=0.001, max_value=0.5),
                ParamSpec("max_profit_pct", float, default=0.10, min_value=0.001, max_value=2.0),
                ParamSpec("max_trades", int, default=10, min_value=1, max_value=1000)
            ],
            inputs=[
                IOSpec("orders", "Orders")
            ],
            outputs=[
                IOSpec("filtered_orders", "Orders")
            ]
        ))


# Singleton registry
_registry = None

def get_registry() -> NodeRegistry:
    """Get the global node registry."""
    global _registry
    if _registry is None:
        _registry = NodeRegistry()
    return _registry
