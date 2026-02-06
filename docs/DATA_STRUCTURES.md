# Data Structures Reference

## Strategy Graph JSON

A strategy graph defines a trading strategy as a directed acyclic graph (DAG) of nodes. Each node represents an indicator, signal, or order generation step.

### Complete Example

```json
{
  "graph_id": "strategy_abc123",
  "name": "SMA Crossover with RSI Filter",
  "version": "1.0",
  "universe": {
    "type": "explicit",
    "symbols": ["AAPL", "MSFT", "GOOGL"]
  },
  "time": {
    "timeframe": "5m",
    "date_range": {
      "start": "2024-01-01",
      "end": "2024-12-31"
    }
  },
  "constraints": {
    "max_position_size": 10000.0,
    "max_daily_trades": 10
  },
  "nodes": [
    {
      "id": "market_data",
      "type": "MarketData",
      "params": {},
      "inputs": {}
    },
    {
      "id": "sma_fast",
      "type": "SMA",
      "params": {
        "period": 10
      },
      "inputs": {
        "series": ["market_data", "close"]
      }
    },
    {
      "id": "sma_slow",
      "type": "SMA",
      "params": {
        "period": 30
      },
      "inputs": {
        "series": ["market_data", "close"]
      }
    },
    {
      "id": "rsi",
      "type": "RSI",
      "params": {
        "period": 14
      },
      "inputs": {
        "series": ["market_data", "close"]
      }
    },
    {
      "id": "crossover",
      "type": "Compare",
      "params": {
        "op": ">"
      },
      "inputs": {
        "a": ["sma_fast", "value"],
        "b": ["sma_slow", "value"]
      }
    },
    {
      "id": "rsi_filter",
      "type": "Compare",
      "params": {
        "op": "<"
      },
      "inputs": {
        "a": ["rsi", "rsi"],
        "b": ["const_70", "value"]
      }
    },
    {
      "id": "const_70",
      "type": "Constant",
      "params": {
        "value": 70.0
      },
      "inputs": {}
    },
    {
      "id": "entry_signal",
      "type": "And",
      "params": {},
      "inputs": {
        "a": ["crossover", "result"],
        "b": ["rsi_filter", "result"]
      }
    },
    {
      "id": "orders",
      "type": "orders",
      "params": {
        "side": "long",
        "qty": 100
      },
      "inputs": {
        "entry_signal": ["entry_signal", "result"]
      }
    }
  ],
  "outputs": {
    "orders": ["orders", "orders"]
  },
  "metadata": {
    "description": "SMA crossover with RSI overbought filter",
    "created_at": "2024-01-15T10:30:00",
    "parent_graph_id": "strategy_xyz789",
    "generation": 3
  }
}
```

### Key Fields

| Field | Type | Description |
|-------|------|-------------|
| `graph_id` | string | Unique identifier (auto-generated) |
| `name` | string | Human-readable strategy name |
| `version` | string | Version (default "1.0") |
| `universe` | UniverseSpec | Symbols to trade |
| `time` | TimeConfig | Timeframe and date range |
| `constraints` | ExecutionConstraints | Position limits, risk controls |
| `nodes` | Node[] | List of computation nodes |
| `outputs` | dict | Output mapping (name → [node_id, output_key]) |
| `metadata` | dict | Optional metadata (description, parent, generation) |

### Node Structure

Each node has:

```typescript
interface Node {
  id: string;                    // Unique node ID
  type: string;                  // Node type (SMA, RSI, Compare, etc.)
  params: Record<string, any>;   // Node-specific parameters
  inputs: Record<string, [string, string]>;  // input_name → [node_id, output_key]
}
```

**Example Node Types:**
- **Indicators:** `SMA`, `EMA`, `RSI`, `MACD`, `BBands`, `ATR`
- **Comparisons:** `Compare` (>, <, ==), `And`, `Or`, `Not`
- **Signals:** `EntrySignal`, `ExitSignal`
- **Orders:** `orders`, `BracketOrder`, `MarketOrder`
- **Risk:** `RiskManagerDaily`, `PositionSizingFixed`, `StopLossFixed`
- **Utility:** `Constant`, `MarketData`

---

## Validation Test Results

Validation results contain comprehensive performance metrics across train/holdout splits, stability tests, and jitter tests.

### Phase 2 (Legacy) Validation Result

```json
{
  "strategy_id": "strategy_abc123",
  "strategy_name": "SMA Crossover with RSI Filter",
  "timestamp": "2024-01-15T14:30:00",
  "train_results": {
    "total_return": 0.1523,
    "sharpe_ratio": 1.45,
    "max_drawdown": 0.0823,
    "num_trades": 142,
    "win_rate": 0.58,
    "avg_trade_return": 0.0011,
    "profit_factor": 1.67
  },
  "holdout_results": {
    "total_return": 0.0987,
    "sharpe_ratio": 1.12,
    "max_drawdown": 0.0645,
    "num_trades": 52,
    "win_rate": 0.54,
    "avg_trade_return": 0.0019,
    "profit_factor": 1.42
  },
  "stability_test": {
    "k_windows": 6,
    "mean_return": 0.0823,
    "std_return": 0.0234,
    "min_return": 0.0456,
    "max_return": 0.1123,
    "concentration_penalty": 0.15,
    "cliff_penalty": 0.08
  },
  "jitter_test": {
    "n_runs": 10,
    "jitter_pct": 0.1,
    "mean_return": 0.0945,
    "std_return": 0.0167,
    "sign_flip_penalty": 0.05,
    "fragility_score": 0.22
  },
  "fitness_score": 0.0734,
  "penalties": {
    "concentration": 0.15,
    "cliff": 0.08,
    "sign_flip": 0.05,
    "fragility": 0.22
  },
  "failure_labels": [
    "concentrated_returns",
    "parameter_fragile"
  ]
}
```

### Phase 3 (Episode-Based) Validation Result

```json
{
  "strategy_id": "strategy_abc123",
  "strategy_name": "SMA Crossover with RSI Filter",
  "timestamp": "2026-02-06T12:00:00",
  "phase3": {
    "aggregated_fitness": 0.042,
    "median_fitness": 0.055,
    "worst_fitness": -0.120,
    "best_fitness": 0.180,
    "std_fitness": 0.085,

    "worst_case_penalty": 0.0,
    "dispersion_penalty": 0.0,
    "single_regime_penalty": 0.0,
    "lucky_spike_penalty": 0.0,

    "regime_coverage": {
      "unique_regimes": 8,
      "years_covered": [2020, 2021, 2022],
      "regime_counts": {
        "(('trend', 'up'), ('vol_bucket', 'mid'), ('chop_bucket', 'trending'), ('drawdown_state', 'at_highs'))": 2,
        "(('trend', 'down'), ('vol_bucket', 'high'), ('chop_bucket', 'choppy'), ('drawdown_state', 'in_drawdown'))": 1,
        "(('trend', 'flat'), ('vol_bucket', 'low'), ('chop_bucket', 'trending'), ('drawdown_state', 'recovering'))": 3
      },
      "per_regime_fitness": {
        "(('trend', 'up'), ('vol_bucket', 'mid'), ('chop_bucket', 'trending'), ('drawdown_state', 'at_highs'))": [0.085, 0.092],
        "(('trend', 'down'), ('vol_bucket', 'high'), ('chop_bucket', 'choppy'), ('drawdown_state', 'in_drawdown'))": [-0.120],
        "(('trend', 'flat'), ('vol_bucket', 'low'), ('chop_bucket', 'trending'), ('drawdown_state', 'recovering'))": [0.045, 0.038, 0.052]
      }
    },

    "n_trades_per_episode": [23, 18, 31, 27, 19, 25, 22, 29],

    "explanation": {
      "decision": "survive",
      "reasons": [
        "Positive aggregated fitness (0.042) with acceptable dispersion"
      ],
      "penalties_applied": [],
      "total_penalty": 0.0,
      "episodes_evaluated": 8,
      "episodes_failed": 1,
      "regimes_covered": 8,
      "years_covered": [2020, 2021, 2022]
    },

    "episodes": [
      {
        "label": "episode_1",
        "start_ts": "2020-03-15T09:30:00",
        "end_ts": "2020-06-20T16:00:00",
        "fitness": 0.085,
        "decision": "survive",
        "kill_reason": [],
        "tags": {
          "trend": "up",
          "vol_bucket": "mid",
          "chop_bucket": "trending",
          "drawdown_state": "at_highs"
        },
        "difficulty": 0.1,
        "error_details": null,
        "debug_stats": {
          "bars_in_episode": 1234,
          "bars_after_warmup": 1204,
          "signal_true_count": 345,
          "entries_attempted": 23,
          "entries_blocked_by_risk": 0,
          "orders_submitted": 23,
          "fills": 23,
          "exits": 23,
          "feature_nan_pct": {
            "open": 0.0,
            "high": 0.0,
            "low": 0.0,
            "close": 0.0,
            "volume": 0.0
          },
          "key_thresholds": {}
        }
      },
      {
        "label": "episode_2",
        "start_ts": "2021-01-04T09:30:00",
        "end_ts": "2021-03-28T16:00:00",
        "fitness": -0.120,
        "decision": "kill",
        "kill_reason": ["negative_fitness"],
        "tags": {
          "trend": "down",
          "vol_bucket": "high",
          "chop_bucket": "choppy",
          "drawdown_state": "in_drawdown"
        },
        "difficulty": 0.9,
        "error_details": null,
        "debug_stats": {
          "bars_in_episode": 987,
          "bars_after_warmup": 957,
          "signal_true_count": 234,
          "entries_attempted": 18,
          "entries_blocked_by_risk": 5,
          "orders_submitted": 13,
          "fills": 13,
          "exits": 13,
          "feature_nan_pct": {
            "open": 0.0,
            "high": 0.0,
            "low": 0.0,
            "close": 0.0,
            "volume": 0.0
          },
          "key_thresholds": {}
        }
      }
    ]
  }
}
```

---

## Evaluation Result (StrategyEvaluationResult)

The canonical result object returned from evaluation:

```json
{
  "graph_id": "strategy_abc123",
  "strategy_name": "SMA Crossover with RSI Filter",
  "validation_report": { /* Phase 2 or Phase 3 report (see above) */ },
  "fitness": 0.042,
  "decision": "survive",
  "kill_reason": []
}
```

**Decision Types:**
- `"survive"` - Strategy passed evaluation
- `"kill"` - Strategy failed evaluation
- `"mutate_only"` - Strategy killed but in grace period (can still mutate)

**Common Kill Reasons:**
- `"negative_fitness"` - Fitness score < 0
- `"no_holdout_trades"` - No trades in holdout period
- `"too_few_holdout_trades"` - < 3 trades in holdout
- `"too_few_holdout_days"` - Trades on < 3 unique days
- `"severe_holdout_degradation"` - Holdout < 30% of train
- `"holdout_sign_flip"` - Positive train, negative holdout
- `"phase3_negative_aggregate"` - Negative aggregated fitness (Phase 3)
- `"phase3_dispersion"` - High dispersion across episodes (Phase 3)

---

## Blue Memo (Per-Strategy Self-Advocacy)

```json
{
  "run_id": "20260206_120000",
  "graph_id": "child_gen2_005",
  "parent_graph_id": "child_gen1_003",
  "generation": 2,
  "mutation_patch_summary": [
    "add_node: RSI",
    "modify_param: sma_fast.period = 8",
    "rewire: entry_signal.b <- rsi_filter.result"
  ],
  "claim": "Applied mutations: add_node: RSI; modify_param: sma_fast.period = 8; rewire: entry_signal.b <- rsi_filter.result",
  "expected_improvement": [
    "Reduce fitness dispersion across episodes",
    "Better performance during drawdown regimes",
    "Eliminate lucky spike dependency"
  ],
  "risks": [
    "Increased complexity may reduce robustness",
    "Parameter sensitivity to lookback periods"
  ],
  "created_at": "2026-02-06T12:15:30"
}
```

---

## Red Verdict (Global Overseer Judgment)

```json
{
  "run_id": "20260206_120000",
  "graph_id": "child_gen2_005",
  "verdict": "KILL",
  "top_failures": [
    {
      "code": "LUCKY_SPIKE",
      "severity": 0.9,
      "evidence": "Best episode dominates: penalty=0.20"
    },
    {
      "code": "HIGH_DISPERSION",
      "severity": 0.6,
      "evidence": "High variance: worst=-0.300, median=0.100, penalty=0.30"
    },
    {
      "code": "LOW_YEARS_COVERED",
      "severity": 0.7,
      "evidence": "Only 1 year(s) covered: [2020]"
    }
  ],
  "strongest_evidence": [
    "Best episode dominates: penalty=0.20",
    "High variance: worst=-0.300, median=0.100, penalty=0.30",
    "Only 1 year(s) covered: [2020]"
  ],
  "next_action": {
    "type": "RESEARCH_TRIGGER",
    "suggestion": "Consider targeted research on lucky spike solutions"
  },
  "metrics_summary": {
    "episodes_count": 8,
    "years_covered": [2020],
    "lucky_spike_triggered": true,
    "median_return": 0.1,
    "dispersion": 0.25,
    "regime_count": 4
  },
  "created_at": "2026-02-06T12:15:30"
}
```

**Verdict Types:**
- `"SURVIVE"` - Strategy passed
- `"KILL"` - Strategy failed

**Failure Codes:**
- `"LUCKY_SPIKE"` - Best episode > 60% of total positive fitness
- `"HIGH_DISPERSION"` - High variance across episodes
- `"LOW_YEARS_COVERED"` - Fewer than 2 years covered
- `"DRAWDOWN_FAIL"` - >50% of drawdown/recovering episodes failed
- `"SINGLE_REGIME_DEPENDENT"` - Only profitable in one regime
- `"NEGATIVE_AGGREGATE"` - Overall negative fitness

**Next Action Types:**
- `"MUTATE"` - Continue evolution with mutations
- `"STOP_BRANCH"` - No viable path forward
- `"RESEARCH_TRIGGER"` - Consider targeted research
- `"NONE"` - No specific action

---

## Metrics Summary

### Key Performance Metrics

All metrics are returned in validation reports. Here's a comprehensive list:

#### Returns Metrics
```typescript
{
  total_return: number;        // Cumulative return (e.g., 0.1523 = 15.23%)
  avg_trade_return: number;    // Average per-trade return
  median_fitness: number;      // Median across episodes (Phase 3)
  worst_fitness: number;       // Worst episode fitness (Phase 3)
  best_fitness: number;        // Best episode fitness (Phase 3)
  aggregated_fitness: number;  // Final fitness after penalties (Phase 3)
}
```

#### Risk Metrics
```typescript
{
  sharpe_ratio: number;        // Risk-adjusted return (>1.0 = good)
  max_drawdown: number;        // Maximum peak-to-trough decline (0.0823 = 8.23%)
  std_fitness: number;         // Standard deviation of fitness across episodes
  dispersion_penalty: number;  // Penalty for high variance (Phase 3)
  worst_case_penalty: number;  // Penalty for very bad episodes (Phase 3)
}
```

#### Trading Metrics
```typescript
{
  num_trades: number;              // Total number of trades
  n_trades_per_episode: number[];  // Trades per episode (Phase 3)
  win_rate: number;                // Fraction of winning trades (0.58 = 58%)
  profit_factor: number;           // Gross profit / gross loss (>1.0 = profitable)
  entries_attempted: number;       // Number of entry signals generated
  entries_blocked_by_risk: number; // Entries blocked by risk manager
  fills: number;                   // Successful order fills
}
```

#### Robustness Metrics (Phase 3)
```typescript
{
  unique_regimes: number;          // Number of unique market regimes covered
  years_covered: number[];         // List of calendar years covered
  lucky_spike_penalty: number;     // Penalty for best episode dominance
  single_regime_penalty: number;   // Penalty for regime dependence
  episodes_evaluated: number;      // Total episodes sampled
  episodes_failed: number;         // Episodes with negative fitness
}
```

#### Stability Metrics (Phase 2)
```typescript
{
  concentration_penalty: number;   // Penalty for returns concentrated in one window
  cliff_penalty: number;           // Penalty for second-half performance drop
  sign_flip_penalty: number;       // Penalty for parameter sensitivity
  fragility_score: number;         // Overall parameter fragility (0-1)
}
```

---

## Research Pack

```json
{
  "id": "0dfdb8f9ef66576a",
  "created_at": "2026-02-06T12:00:00",
  "query": "mean reversion trading strategies",
  "provider": "youcom",
  "sources": [
    {
      "title": "Mean Reversion Trading: A Complete Guide",
      "url": "https://example.com/mean-reversion-guide",
      "snippet": "Mean reversion strategies assume that prices tend to return to their average over time. Key indicators include Bollinger Bands, RSI, and moving averages...",
      "provider_rank": 1,
      "published_date": "2024-03-15"
    },
    {
      "title": "Statistical Arbitrage and Mean Reversion",
      "url": "https://example.com/stat-arb",
      "snippet": "Statistical properties of mean reversion: assumes normal distribution of returns, stationarity, and finite variance...",
      "provider_rank": 2,
      "published_date": "2023-11-20"
    }
  ],
  "extracted": {
    "assumptions": [
      "Assumes price returns follow known statistical properties",
      "Assumes trends persist over signal window",
      "Assumes sufficient liquidity for execution"
    ],
    "knobs": [
      "Lookback period / window size",
      "Signal threshold levels",
      "Risk management parameters (SL/TP)",
      "Position sizing / allocation weights"
    ],
    "known_failure_modes": [
      "Overfitting to historical patterns",
      "Regime change / non-stationarity",
      "Slippage and execution costs",
      "Excessive drawdown during volatile periods"
    ],
    "suggested_tests": [
      "Walk-forward out-of-sample validation",
      "Monte Carlo / bootstrap robustness testing",
      "Cross-regime performance evaluation",
      "Parameter sensitivity analysis",
      "Drawdown stress testing"
    ]
  },
  "raw": {
    "query": "mean reversion trading strategies",
    "n_results": 5,
    "source_count": 2
  },
  "fingerprint": "sha256:0dfdb8f9ef66576a1234567890abcdef..."
}
```

---

## Regime Tags (Phase 3)

Each episode is tagged with market regime characteristics:

```typescript
interface RegimeTags {
  trend: "up" | "down" | "flat";              // Price trend (>3%, <-3%, or between)
  vol_bucket: "low" | "mid" | "high";         // Volatility vs historical ATR
  chop_bucket: "trending" | "choppy";         // Directional vs rangebound (ratio >0.4)
  drawdown_state: "in_drawdown" | "recovering" | "at_highs";  // Drawdown level (>10%, 3-10%, <3%)
}
```

**Example:**
```json
{
  "trend": "down",
  "vol_bucket": "high",
  "chop_bucket": "choppy",
  "drawdown_state": "in_drawdown"
}
```

This represents a **hard regime** - downtrending, high volatility, choppy (not directional), and in significant drawdown. Strategies that perform well here are more robust.

---

## Difficulty Score

Each episode gets a difficulty score (0.0-1.0) based on regime tags:

```typescript
difficulty =
  (vol_bucket === "high" ? 0.3 : vol_bucket === "mid" ? 0.1 : 0) +
  (chop_bucket === "choppy" ? 0.3 : 0) +
  (trend === "down" ? 0.2 : trend === "flat" ? 0.1 : 0) +
  (drawdown_state === "in_drawdown" ? 0.2 : drawdown_state === "recovering" ? 0.1 : 0)
```

**Examples:**
- Easy (0.0-0.3): Uptrending, low vol, trending, at highs
- Medium (0.3-0.6): Mixed conditions
- Hard (0.6-1.0): Downtrending, high vol, choppy, in drawdown

---

## Summary Table of All Metrics

| Category | Metric | Range | Good Value | Phase |
|----------|--------|-------|------------|-------|
| **Returns** | total_return | -1.0 to ∞ | >0.05 (5%) | 2, 3 |
| | median_fitness | -∞ to ∞ | >0.03 | 3 |
| | aggregated_fitness | -∞ to ∞ | >0.02 | 3 |
| **Risk** | sharpe_ratio | -∞ to ∞ | >1.0 | 2, 3 |
| | max_drawdown | 0.0 to 1.0 | <0.15 (15%) | 2, 3 |
| | std_fitness | 0.0 to ∞ | <0.20 | 3 |
| **Trading** | num_trades | 0 to ∞ | >10 | 2, 3 |
| | win_rate | 0.0 to 1.0 | >0.50 (50%) | 2 |
| | profit_factor | 0.0 to ∞ | >1.3 | 2 |
| **Robustness** | unique_regimes | 0 to ∞ | >5 | 3 |
| | years_covered | [] | ≥2 years | 3 |
| | lucky_spike_penalty | 0.0 to 0.2 | 0.0 | 3 |
| | episodes_failed | 0 to n | <50% | 3 |
| **Stability** | concentration_penalty | 0.0 to 1.0 | <0.3 | 2 |
| | fragility_score | 0.0 to 1.0 | <0.4 | 2 |

---

This reference covers all major data structures and metrics in the system. All JSON examples are production-ready and match the actual backend implementation.
