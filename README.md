# Darwinian Strategy Backtester

A deterministic, graph-based backtesting engine for equity trading strategies with evolutionary optimization capabilities.

## Overview

This system transforms natural language trading ideas into validated, executable strategy graphs that evolve through Darwinian selection with brutal anti-overfitting validation. Built for serious quantitative research with strict no-lookahead guarantees and deterministic execution.

**Key Features:**
- **Graph-based DSL**: Strategies as directed acyclic graphs of composable nodes
- **Deterministic Execution**: Strict time ordering, no lookahead bias
- **20+ Node Types**: Technical indicators, logic operators, risk management
- **Realistic Backtesting**: Next-bar fills, intrabar stop/target checking
- **Performance Analytics**: Sharpe, CAGR, drawdown, win rate, profit factor
- **Evolution Ready**: Designed for LLM-driven strategy mutation (Phase 2)

## Architecture

```
Strategy Flow:
Natural Language → StrategyGraph JSON → Graph Executor → Backtest Simulator → Metrics

Example:
"Buy when 10 SMA crosses above 50 SMA, stop at 1.5x ATR"
    ↓
{nodes: [MarketData, SMA(10), SMA(50), Compare(cross_up), ...]}
    ↓
Topological execution with validated data flow
    ↓
Trade-by-trade simulation with risk management
    ↓
{sharpe: 1.2, cagr: 15%, max_dd: -8%, ...}
```

## Project Structure

```
darwinian-backtester/
├── config.py                 # Configuration and environment
├── requirements.txt          # Python dependencies
│
├── data/                     # Data acquisition
│   └── polygon_client.py     # Polygon.io API with caching
│
├── graph/                    # Strategy graph system
│   ├── schema.py             # Pydantic models for StrategyGraph
│   ├── gene_pool.py          # Node type registry (gene pool)
│   └── executor.py           # Graph execution engine
│
├── backtest/                 # Backtesting engine
│   └── simulator.py          # Trade simulator with metrics
│
├── validation/               # Anti-overfitting validation suite
│   ├── overfit_tests.py      # Train/holdout, stability, jitter
│   ├── fitness.py            # Fitness scoring with penalties
│   ├── reporting.py          # ValidationReport generation
│   ├── evaluation.py         # Survival gate with kill labels
│   └── robust_eval.py        # Multi-symbol robustness mode
│
├── llm/                      # LLM integration
│   ├── compile.py            # NL → StrategyGraph compilation
│   ├── mutate.py             # Graph mutation generation
│   ├── client_openai.py      # OpenAI client with caching
│   ├── client_anthropic.py   # Anthropic client with caching
│   ├── cache.py              # Response caching & budget tracking
│   ├── json_guard.py         # JSON validation & repair
│   └── results_summary.py    # Compact evaluation summaries
│
├── evolution/                # Darwinian evolution engine
│   ├── darwin.py             # Multi-generation evolution loop
│   ├── patches.py            # Patch models & application
│   ├── population.py         # Population utilities
│   └── storage.py            # Run persistence
│
├── backend_api/              # FastAPI backend
│   └── main.py               # REST API + SSE streaming
│
└── frontend/                 # React viewer
    ├── src/
    │   ├── pages/            # RunsList, RunDetail, StrategyDetail
    │   ├── components/       # GraphViewer (react-flow)
    │   └── lib/              # API client
    └── package.json
```

## Prerequisites

- **Python 3.11+**
- **API Keys:**
  - [Polygon.io](https://polygon.io) - Market data (required)
  - [OpenAI](https://openai.com) - Strategy compilation (Phase 2)
  - [Anthropic](https://anthropic.com) - Strategy mutations (Phase 2)

## Installation

1. **Clone or download this repository**

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure API keys:**
   ```bash
   cp .env.example .env
   # Edit .env and add your API keys
   ```

4. **Verify installation:**
   ```bash
   python demo_sma_crossover.py
   ```

## Quick Start

### Run Evolution Demo

Run a complete Darwinian evolution with LLM-driven mutations:

```bash
python demo_darwin.py
```

This will:
1. Compile a natural language strategy into a StrategyGraph
2. Evolve through 3 generations with mutations
3. Apply brutal anti-overfitting validation (train/holdout, stability, jitter)
4. Save all artifacts to `results/runs/<run_id>/`

### Run Basic Backtest Demo

The demo implements a classic SMA crossover strategy:
- **Entry**: Fast SMA (10) crosses above Slow SMA (50)
- **Exit**: Fast SMA crosses below Slow SMA
- **Stop Loss**: 1.5x ATR
- **Take Profit**: 3x ATR
- **Position Size**: $10,000 per trade
- **Risk Limits**: Max 2% daily loss, 10% daily profit, 10 trades/day

```bash
python demo_sma_crossover.py
```

**Expected Output:**
```
SMA CROSSOVER STRATEGY DEMO
============================================================

📈 Creating SMA Crossover strategy (10/50 periods)...
✓ Validating strategy graph...
✓ Graph structure valid

📊 Fetching AAPL 5m data (2024-10-01 to 2025-01-01)...
✓ Fetched 9,234 bars

⚙️  Executing strategy graph...
✓ Graph executed successfully (26 outputs)

🔬 Running backtest simulation...
✓ Backtest complete

============================================================
BACKTEST RESULTS
============================================================

Returns:
  Total Return:        $3,245.67 (3.25%)
  CAGR:                12.45%

Risk Metrics:
  Sharpe Ratio:        1.23
  Max Drawdown:        $-1,234.56 (-1.23%)

Trade Statistics:
  Total Trades:        42
  Win Rate:            57.14%
  Average Win:         $245.32
  Average Loss:        $-156.78
  Profit Factor:       1.85
  Avg Trade Duration:  3.2 hours

============================================================

📊 Equity curve saved to: equity_curve.png

✅ Demo complete!
```

### Custom Strategy Example

```python
from graph.schema import StrategyGraph, Node
from graph.executor import GraphExecutor
from backtest.simulator import run_backtest
from data.polygon_client import PolygonClient

# Create your strategy graph
strategy = StrategyGraph(
    graph_id="my_strategy_001",
    name="My Custom Strategy",
    nodes=[
        Node(id="market_data", type="MarketData", params={}, inputs={}),
        Node(id="rsi", type="RSI", params={"period": 14},
             inputs={"series": ("market_data", "close")}),
        # ... more nodes
    ],
    outputs={"orders": ("risk_manager", "filtered_orders")},
    # ... universe, time config, etc.
)

# Fetch data
client = PolygonClient()
data = client.get_bars("AAPL", "5m", "2024-01-01", "2024-12-31")

# Execute graph
executor = GraphExecutor()
context = executor.execute(strategy, data)

# Run backtest
results = run_backtest(
    data=data,
    orders_config=context[("risk_manager", "filtered_orders")],
    initial_capital=100000.0
)

# Analyze results
print(results['metrics'])
```

## Available Node Types

### Data & Time
- `MarketData` - Provides OHLCV series

### Technical Indicators
- `SMA` - Simple Moving Average
- `EMA` - Exponential Moving Average
- `RSI` - Relative Strength Index
- `ATR` - Average True Range
- `BBands` - Bollinger Bands
- `MACD` - Moving Average Convergence Divergence
- `Returns` - Price returns over lookback period
- `ZScore` - Rolling z-score normalization

### Logic & Comparison
- `Compare` - Comparison operators (>, <, >=, <=, ==, cross_up, cross_down, between)
- `And` - Logical AND
- `Or` - Logical OR
- `Not` - Logical NOT

### Signals
- `EntrySignal` - Entry signal generator
- `ExitSignal` - Exit signal generator

### Risk Management & Orders
- `StopLossFixed` - Fixed point stop loss
- `StopLossATR` - ATR-based stop loss
- `TakeProfitFixed` - Fixed point take profit
- `TakeProfitATR` - ATR-based take profit
- `PositionSizingFixed` - Fixed dollar position sizing
- `PositionSizingPct` - Percentage of equity sizing
- `BracketOrder` - Bracket order constructor
- `RiskManagerDaily` - Daily risk limits (P&L caps, max trades)

## Execution Model

### No-Lookahead Guarantees
- All signals generated at bar close
- All fills occur at next bar open
- Indicators use proper rolling windows
- No future data leakage

### Position Management
- Single position at a time
- Entry: Signal at `t` close → Fill at `t+1` open
- Exit: Signal/Stop/Target → Fill at `t+1` open or intrabar
- Stop/Target checked using bar high/low
- Worst-case assumption: Stop hit before target if both triggered

### Risk Management
- Daily P&L limits (max loss %, max profit %)
- Daily trade count limits
- Auto-reset at day boundaries
- Pre-trade risk checks

## Performance Metrics

### Returns
- Total Return ($, %)
- CAGR (annualized)

### Risk
- Sharpe Ratio (annualized, timeframe-adjusted)
- Max Drawdown ($, %)

### Trade Statistics
- Win Rate
- Average Win/Loss
- Profit Factor
- Trade Count
- Average Trade Duration

## Roadmap

### Phase 1-3.5: Core Engine ✅
- [x] Graph schema and validation
- [x] Node registry (gene pool)
- [x] Graph executor
- [x] Backtest simulator
- [x] Performance metrics
- [x] Demo scripts

### Phase 4-4.75: Anti-Overfitting Validation ✅
- [x] Train/holdout split validation
- [x] Subwindow stability testing
- [x] Parameter jitter testing
- [x] Fitness scoring with penalties
- [x] Survival gate with 8 kill labels
- [x] Deterministic evaluation pipeline

### Phase 5: LLM Integration ✅
- [x] Natural language → StrategyGraph compilation
- [x] Graph mutation generation
- [x] Response caching & budget tracking
- [x] JSON validation & repair

### Phase 6-6.5: Darwinian Evolution ✅
- [x] Multi-generation evolution loop
- [x] Patch-based mutations with budget enforcement
- [x] Population management & lineage tracking
- [x] Run persistence & storage
- [x] Multi-symbol robustness mode

### Phase 7-7.5: Web Viewer ✅ (Current)
- [x] FastAPI backend with SSE streaming
- [x] React frontend with react-flow
- [x] Run browsing and strategy visualization
- [x] Real-time run monitoring with live progress
- [x] New run form with presets
- [x] Event log with auto-scroll and pause
- [x] Progress tracking (evals, generation, fitness, budget)

### Phase 8+: Future Features
- [ ] Graph editing UI
- [ ] Mutation buttons in viewer
- [ ] Multi-timeframe robustness testing
- [ ] Walk-forward analysis
- [ ] Live trading integration

## Design Principles

1. **Determinism First**: Same inputs → same outputs, always
2. **No Lookahead**: Future data never influences past decisions
3. **Realistic Execution**: Model real-world fills, slippage, risk limits
4. **Composability**: Build complex strategies from simple nodes
5. **Evolvability**: Graph structure designed for mutation and selection
6. **Brutal Validation**: Assume overfitting until proven otherwise

## Data Sources

- **Polygon.io**: OHLCV bars (1min, 5min, 15min, 1hour, 1day)
- Cached locally as parquet files (7-day expiry)
- Adjusted prices (splits, dividends)

## Constraints

- Equities only (no futures, options, crypto)
- US markets only
- Regular trading hours (9:30 AM - 4:00 PM ET)
- No overnight positions (Phase 1)
- Single symbol per backtest (multi-symbol in Phase 2)

## Running the Web Viewer

After running some Darwin evolution runs, you can browse results in the web viewer:

1. **Start the backend:**
   ```bash
   cd backend_api
   python main.py
   ```
   Backend runs on `http://localhost:8050`

2. **Start the frontend:**
   ```bash
   cd frontend
   npm install  # first time only
   npm run dev
   ```
   Frontend runs on `http://localhost:5173`

3. **Open browser** to `http://localhost:5173`

Features:
- Browse all evolution runs
- View lineage trees and top strategies
- Visualize strategy graphs with react-flow
- Inspect evaluation results and failure labels
- View patch operations applied to strategies

See [frontend/README.md](frontend/README.md) for more details.

## Backend Debug Helpers

- `POST /api/presence/heartbeat`, `GET /api/presence/history`, `GET /api/repos/context` — placeholder
  responses to keep auxiliary tooling (workspace presence trackers, dev proxies)
  from spamming 404s; they echo the workspace/repo identifiers you pass.
- `GET /api/conflict-signals` and `/api/conflict-signals/active` — return empty signal
  sets with the provided filters so external monitors can poll without failing.
- `GET /api/debug/requests` and `/api/debug/errors` — expose the last ~250 requests
  and ~50 errors with timestamps, headers, and tracebacks for faster debugging.


## Troubleshooting

### "POLYGON_API_KEY not set"
Create a `.env` file in the project root with your API key:
```
POLYGON_API_KEY=your_key_here
```

### "No data returned"
- Check your Polygon subscription tier (free tier has limited history)
- Verify date range is valid
- Ensure symbol is correct (uppercase, e.g., "AAPL")

### Import errors
Install dependencies:
```bash
pip install -r requirements.txt
```

### Graph validation errors
- Check all node IDs are unique
- Verify all input references exist
- Ensure no circular dependencies
- Validate required parameters are set

## Contributing

This is a research project. Focus areas:
- Bug fixes in execution logic
- Additional technical indicators
- Performance optimizations
- Documentation improvements

## License

MIT License - See LICENSE file for details

## Acknowledgments

Built for quantitative researchers who believe:
- Markets are hard
- Overfitting is the default
- Simplicity beats complexity
- Evolution beats optimization

---

**Status**: Phase 7 Complete (Web Viewer)
**Next**: Real-time run monitoring, graph editing UI
