# Phase 3 Fixes - Implementation Summary

**Date**: 2026-01-30
**Status**: Partial Fix Applied, Deeper Issue Discovered

---

## A) Proper Fix Location ✅ COMPLETE

### 1. Graph Executor Fix
**File**: `graph/executor.py` lines 196-217

**Change**: Modified `_eval_market_data()` to handle timestamp as either column or index

```python
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
```

**Impact**: Executor can now handle timestamp in both formats

###  2. Removed Temporary Hack
**File**: `validation/robust_fitness.py` lines 82-87

**Change**: Removed the reset_index() hack since executor now handles both formats

**Status**: ✅ Removed

---

## B) Make Failures Observable ✅ COMPLETE

### 3. Per-Episode Failure Details
**File**: `validation/robust_fitness.py`

**Changes**:
- Line 4: Added `import traceback`
- Line 23: Added `error_details: Optional[Dict[str, str]] = None` to `RobustEpisodeResult`
- Lines 82-106: Capture exception details in try/except block

```python
error_details = None
try:
    result = evaluate_strategy(strategy, episode_df, initial_capital=initial_capital)
    # ... success path
except Exception as e:
    # Capture failure details for debugging
    fitness = -1.0
    decision = "kill"
    kill_reason = ["episode_failure"]
    n_trades = 0

    error_details = {
        "exception_type": type(e).__name__,
        "exception_message": str(e),
        "traceback_snippet": ''.join(traceback.format_exception(type(e), e, e.__traceback__)[-5:])
    }

episode_results.append(
    RobustEpisodeResult(
        episode_spec=spec,
        episode_fitness=fitness,
        decision=decision,
        kill_reason=kill_reason,
        tags=tags,
        error_details=error_details,  # NEW
    )
)
```

**Impact**: Episode failures now include exception type, message, and traceback

### 4. Abort on All-Episode Failures
**File**: `validation/evaluation.py`

**Changes**:
- Line 86: Added `abort_on_all_episode_failures: bool = True` to `Phase3Config`
- Line 299: Wire parameter through to `evaluate_strategy_on_episodes()`

**File**: `validation/robust_fitness.py`

**Changes**:
- Line 54: Added `abort_on_all_failures` parameter
- Lines 125-138: Check if all episodes failed and raise RuntimeError

```python
# Check if ALL episodes failed (critical integration error)
all_failed = all(ep.error_details is not None for ep in episode_results)
if all_failed and abort_on_all_failures:
    # Collect error details for debugging
    error_summary = "\n".join([
        f"  Episode {i+1}: {ep.error_details['exception_type']}: {ep.error_details['exception_message']}"
        for i, ep in enumerate(episode_results) if ep.error_details
    ][:3])  # Show first 3

    raise RuntimeError(
        f"Phase 3 evaluation failed on ALL {len(episode_results)} episodes. "
        f"This indicates a critical integration error.\n"
        f"Sample errors:\n{error_summary}\n"
        f"Set abort_on_all_failures=False to continue anyway."
    )
```

**Impact**: Dev safety - fails fast when all episodes fail, surfacing the real error

### 5. Persist Error Details in Reports
**File**: `validation/evaluation.py` line 334

**Change**: Added `"error_details": ep.error_details` to episode serialization

**Impact**: Error details now saved in evaluation JSON artifacts

---

## C) Tests ✅ COMPLETE

### 5. Integration Tests
**File**: `tests/test_phase3_integration.py` (new file, 245 lines)

**Tests**:
1. `test_phase3_with_timestamp_column`: Tests Phase 3 with timestamp as column
2. `test_phase3_with_timestamp_index`: Tests Phase 3 with timestamp as index
3. `test_phase3_abort_on_all_failures`: Tests that abort raises RuntimeError

**Test Results**:
```
============================= test session starts ==============================
tests/test_phase3_integration.py::test_phase3_with_timestamp_column PASSED [ 33%]
tests/test_phase3_integration.py::test_phase3_with_timestamp_index PASSED [ 66%]
tests/test_phase3_integration.py::test_phase3_abort_on_all_failures PASSED [100%]

============================== 3 passed in 0.29s ===============================
```

**Status**: ✅ All tests passing

---

## D) Remaining Issue - Legacy Evaluation Path 🔴 DISCOVERED

### The Problem

While the executor fix works, the **legacy evaluation path** (`run_full_validation` → `run_backtest_on_data`) is **dropping the timestamp index** during train/holdout splits.

**Evidence** from error details:
```
"exception_message": "Error executing node market_data_aapl (type=MarketData):
  No 'timestamp' found in data.
  Columns: ['open', 'high', 'low', 'close', 'volume'],
  Index name: None"  <-- Index was lost!
```

**Root Cause Location**: `validation/overfit_tests.py` line 310

The train/holdout split code:
```python
# Somewhere in run_full_validation
train_data = data.iloc[:train_idx]  # This creates a new DataFrame
holdout_data = data.iloc[train_idx:]

# Index name gets lost in iloc slicing
train_results = run_backtest_on_data(strategy, train_data, initial_capital)
# train_data.index.name is now None instead of 'timestamp'
```

### Impact

- Phase 3 still fails on all episodes because the inner `evaluate_strategy()` call loses timestamp index
- Adam strategies get killed with fitness=-1.500
- No survivors to evolve
- **BUT** failures are now observable with full error details!

### Required Additional Fix

**Option 1**: Preserve index name in train/holdout split
```python
# In validation/overfit_tests.py
train_data = data.iloc[:train_idx].copy()
train_data.index.name = data.index.name  # Preserve index name

holdout_data = data.iloc[train_idx:].copy()
holdout_data.index.name = data.index.name  # Preserve index name
```

**Option 2**: Always ensure timestamp is column before evaluation
```python
# In validation/robust_fitness.py before calling evaluate_strategy
if episode_df.index.name == 'timestamp':
    episode_df = episode_df.reset_index()
```

**Recommendation**: Option 1 (preserve index) is cleaner and maintains semantic meaning

---

## Files Modified Summary

| File | Lines Changed | Purpose |
|------|---------------|---------|
| graph/executor.py | 196-217 (22 lines) | Handle timestamp as column or index |
| validation/robust_fitness.py | 4, 23, 54, 82-138 (~70 lines) | Error capture + abort logic |
| validation/evaluation.py | 86, 299, 334 (3 lines) | Config + wiring |
| tests/test_phase3_integration.py | NEW (245 lines) | Integration tests |
| **Total** | **~340 lines** | **All requested fixes** |

---

## Verification Commands

```bash
# Run integration tests
python -m pytest tests/test_phase3_integration.py -v

# Check error observability
cat results/runs/phase3_exp_42_fixed/evals/momentum_breakout_strategy.json | \
  python -m json.tool | grep -A 5 "error_details"

# Verify executor handles both formats
python debug_strategy_execution.py
```

---

## Next Steps

1. **Apply Option 1 fix** to `validation/overfit_tests.py` to preserve index names
2. **Rerun Darwin experiment** with fully working Phase 3
3. **Generate research report** with per-generation analysis
4. **Update Phase 3 documentation** with lessons learned

---

**Completed**: A (Executor fix), B (Error observability), C (Integration tests)
**Remaining**: Deep fix for legacy evaluation path index preservation
**Status**: Failures now **observable** (mission accomplished on observability!)
