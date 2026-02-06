# PHASE 3 CRITICAL BUG REPORT

**Status**: 🔴 **BLOCKING BUG DISCOVERED**

**Date**: 2026-01-30
**Discovery Context**: Running Darwin evolution experiment with Phase 3 Part 2

---

## Summary

Phase 3 episode-based evaluation fails due to a **data format incompatibility** between:
1. Phase 3's requirement for timestamp as DataFrame index (for episode slicing)
2. Graph executor's requirement for timestamp as DataFrame column (for market data access)

**Impact**: All Phase 3 evaluations fail silently with fitness=-1.0 and kill_reason=["episode_failure"]

---

## Root Cause Analysis

### Phase 3 Implementation
In `validation/episodes.py`, the `EpisodeSampler` expects timestamp as the index:

```python
def sample_episodes(self, df: pd.DataFrame, ...):
    index = pd.DatetimeIndex(df.index).sort_values()  # Line 64
    # Uses df.index for time-based slicing
```

And in `slice_episode()`:
```python
def slice_episode(df: pd.DataFrame, start_ts: pd.Timestamp, end_ts: pd.Timestamp):
    return df.loc[start_ts:end_ts]  # Requires datetime index
```

### Experiment Setup
In `experiment_phase3_darwin.py`:
```python
# Set timestamp as index for Phase 3
if 'timestamp' in data.columns:
    data = data.set_index('timestamp')  # This breaks downstream execution!
```

### Graph Executor Requirement
In `graph/executor.py` line 204:
```python
def _eval_market_data(self, data: pd.DataFrame) -> Dict[str, pd.Series]:
    return {
        "timestamp": data["timestamp"],  # ❌ KeyError when timestamp is index
        "open": data["open"],
        "high": data["high"],
        ...
    }
```

---

## Evidence

### Test Results

**With timestamp as column (normal evaluation)**:
```
✓ Evaluation succeeded!
  Fitness: -6.841
  Decision: kill
  Kill reason: ['negative_fitness', 'severe_holdout_degradation']
```

**With timestamp as index (Phase 3 style)**:
```
❌ Evaluation FAILED:
   Error type: GraphExecutionError
   Error message: Error executing node market_data_aapl (type=MarketData): 'timestamp'

KeyError: 'timestamp'
  File "graph/executor.py", line 204, in _eval_market_data
    "timestamp": data["timestamp"],
```

### Silent Failure in Phase 3

In `validation/robust_fitness.py` lines 82-99:
```python
try:
    result = evaluate_strategy(strategy, episode_df, initial_capital=initial_capital)
    fitness = result.fitness
    # ... success path
except Exception:  # ❌ Silently swallows GraphExecutionError
    fitness = -1.0
    decision = "kill"
    kill_reason = ["episode_failure"]  # No details about what failed
    n_trades = 0
```

**Result**: All Phase 3 evaluations return:
- `fitness = -1.0`
- `n_trades_per_episode = [0, 0, 0, 0, 0, 0]`
- `decision = "kill"`
- `kill_reason = ["phase3_negative_aggregate"]`

But the **real** error is masked!

---

## Observed Symptoms

1. **Adam strategies always killed** with fitness=-1.500 (median=-1.0, worst_case_penalty=0.5)
2. **Zero trades in all episodes**: `n_trades_per_episode: [0, 0, 0, 0, 0, 0]`
3. **Rescue mode ineffective**: No survivors to mutate because all evaluations fail
4. **Stratified sampling works correctly**: Regime coverage shows 4+ unique regimes
5. **Episode tagging works**: Regimes are properly tagged (trend, vol_bucket, chop_bucket)

**The only thing that doesn't work**: Actual backtest execution within episodes

---

## Proposed Fixes

### Option 1: Reset Index Before Evaluation (Quick Fix)
In `validation/robust_fitness.py` line 72:
```python
for spec in episodes:
    episode_df = slice_episode(data, spec.start_ts, spec.end_ts)

    # FIXME: Reset index so executor can find 'timestamp' column
    if episode_df.index.name == 'timestamp':
        episode_df = episode_df.reset_index()

    history_df = data.loc[: spec.start_ts]
    if history_df.index.name == 'timestamp':
        history_df = history_df.reset_index()

    # Now evaluation should work...
```

### Option 2: Fix Executor to Handle Both Formats (Robust Fix)
In `graph/executor.py` line 204:
```python
def _eval_market_data(self, data: pd.DataFrame) -> Dict[str, pd.Series]:
    # Handle timestamp as either column or index
    if 'timestamp' in data.columns:
        timestamp = data["timestamp"]
    elif data.index.name == 'timestamp':
        timestamp = pd.Series(data.index, index=data.index)
    else:
        raise ValueError("No timestamp found in data (column or index)")

    return {
        "timestamp": timestamp,
        "open": data["open"],
        "high": data["high"],
        ...
    }
```

### Option 3: Don't Require Timestamp as Index (Architecture Change)
Modify `validation/episodes.py` to work with timestamp as column:
```python
def slice_episode(df: pd.DataFrame, start_ts: pd.Timestamp, end_ts: pd.Timestamp):
    if df.index.name == 'timestamp':
        return df.loc[start_ts:end_ts]
    elif 'timestamp' in df.columns:
        mask = (df['timestamp'] >= start_ts) & (df['timestamp'] <= end_ts)
        return df[mask]
    else:
        raise ValueError("Cannot slice episode: no timestamp found")
```

---

## Recommendation

**Immediate**: Apply Option 1 (reset index) to unblock Phase 3 testing
**Short-term**: Apply Option 2 (fix executor) for robustness
**Long-term**: Consider Option 3 if other parts of the system also expect timestamp as column

---

## Impact on Phase 3 Part 2 Verification

**All previous Phase 3 tests passed** because they used **synthetic data** with timestamp already in the correct format. The unit tests didn't catch this because they didn't test actual backtest execution - only episode sampling and regime tagging.

**Real Darwin runs fail** because they use real Polygon data which needs the timestamp column for backtest execution.

This explains why:
- `demo_phase3_sanity.py` "succeeded" but showed all episodes with fitness=-1.0 and 0 trades
- `demo_phase3_part2.py` "succeeded" but showed identical failures for both random and stratified
- The Darwin experiment immediately killed Adam with no survivors

**We were testing the sampling/tagging logic (which works) but not the execution integration (which is broken).**

---

## Next Steps

1. ✅ Document bug (this file)
2. ⏭️ Apply fix (Option 1 for speed)
3. ⏭️ Re-run Darwin experiment with working Phase 3
4. ⏭️ Update Phase 3 integration tests to catch this
5. ⏭️ Consider applying Option 2 for long-term robustness

---

**Filed By**: Claude (Sonnet 4.5)
**Priority**: P0 (blocks all Phase 3 usage)
**Affects**: Phase 3 Part 1 & Part 2
