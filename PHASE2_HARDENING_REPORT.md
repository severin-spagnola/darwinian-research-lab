# Phase 2 Hardening Report
**Date**: 2026-01-29
**Status**: Complete
**Goal**: Eliminate recurring bugs, ensure stable end-to-end execution, improve observability

---

## Summary

Phase 2 hardening successfully resolved **3 critical runtime bugs** and improved system stability, artifact persistence, and LLM transcript capture. The system now runs end-to-end without plumbing/graph/IO failures. Runs may still be killed by fitness validation (as designed), but failures are now deterministic, logged, and visible in the UI.

---

## Critical Bugs Fixed

### Bug #1: Missing Comparison Operator Normalization in Repair Path
**Severity**: High
**Symptom**: `GraphExecutionError: Unknown comparison operator: lt`
**Root Cause**: LLMs output text operators (`"lt"`, `"gt"`, `"greater_than"`) but the Compare node executor expects symbols (`"<"`, `">"`). The initial compile path normalized these correctly, but the **repair path** (when structure validation failed) did not apply comparison operator normalization.

**Fix**:
- Added `_normalize_comparison_operators()` call to repair path in [llm/compile.py:277](llm/compile.py#L277)
- Added operator documentation to system prompt (rule #11)
- Added allowed operators to node documentation for Compare node

**Files Changed**:
- `llm/compile.py` - Added normalization call in repair, enhanced system prompt, documented allowed operators
- `tests/test_operator_normalization.py` - Regression test

**Verification**: ✅ All tests pass, repairs now normalize correctly

---

### Bug #2: Risk Limit Parameters Set to None
**Severity**: High
**Symptom**: `TypeError: unsupported operand type(s) for *: 'float' and 'NoneType'`
**Root Cause**: LLM set `max_profit_pct: None` in RiskManagerDaily when user didn't specify a max profit limit. The backtest simulator then tried to multiply `initial_capital * None`, causing a type error.

**Fix**:
- Modified [backtest/simulator.py:146-164](backtest/simulator.py#L146-L164) to check if risk limit values are `None` before using them
- Changed from:
  ```python
  max_loss = self.initial_capital * risk_limits.get('max_loss_pct', 0.02)
  ```
- To:
  ```python
  max_loss_pct = risk_limits.get('max_loss_pct')
  if max_loss_pct is not None:
      max_loss = self.initial_capital * max_loss_pct
      if daily_pnl < -max_loss:
          continue
  ```

**Files Changed**:
- `backtest/simulator.py` - Added None checks for all risk limit parameters

**Verification**: ✅ Runs complete successfully even when LLM sets partial risk limits

---

### Bug #3: Missing run_id in Backend API → Darwin Call
**Severity**: Medium
**Symptom**: LLM transcripts not saved to per-run directory (`llm_transcripts/`)
**Root Cause**: The backend API wrapper `run_darwin_with_events()` didn't pass `run_id` parameter to the `run_darwin()` function, so transcripts fell back to global `llm_logs/` directory.

**Fix**:
- Modified [backend_api/main.py:571-581](backend_api/main.py#L571-L581) to pass `run_id_param` in kwargs
- Updated `run_darwin_with_events()` to extract and rename `run_id_param` → `run_id` before calling `run_darwin()`

**Files Changed**:
- `backend_api/main.py` - Added run_id passthrough

**Verification**: ✅ Transcripts now saved to `results/runs/{run_id}/llm_transcripts/`

---

### Bug #4: pandas Series Boolean Ambiguity (Fixed in Previous Session)
**Severity**: High
**Symptom**: `ValueError: The truth value of a Series is ambiguous`
**Root Cause**: Using `or` operator on pandas Series objects
**Fix**: Check for `None` explicitly before using fallback
**Files Changed**: `backtest/simulator.py`

---

## Additional Hardening

### Compile Failure Artifact Persistence
**Issue**: If compilation failed, no run directory or artifacts were created, causing 404s in UI
**Fix**:
- Added try/except in [evolution/darwin.py:87-117](evolution/darwin.py#L87-L117) to catch compilation errors
- On failure, creates run directory and saves `summary.json` with `status: "failed_compile"`
- Added `extra` parameter to `storage.save_summary()` for error metadata
- Compile failures now save to `compile_failures/` directory

**Files Changed**:
- `evolution/darwin.py` - Wrapped compilation in try/except
- `evolution/storage.py` - Added `extra` parameter, added `Optional` import

---

### API Endpoint Resilience
**Audit Result**: All critical endpoints already handle missing files gracefully:
- `/api/runs/{run_id}` - Returns partial data if summary missing  ✅
- `/api/runs/{run_id}/lineage` - Returns `{"lineage": []}` if file missing  ✅
- `/api/runs/{run_id}/llm/usage` - Returns default budget if file missing  ✅
- `/api/runs/{run_id}/llm/list` - Returns `{"transcripts": []}` if dir missing  ✅
- `/api/runs/{run_id}/lineage_graph` - Handles empty lineage gracefully  ✅

**No changes needed** - endpoints already resilient.

---

## Test Prompts Verified

Successfully tested with all 3 prompts from task description:

### ✅ Prompt 1: SMA Crossover
```
Buy when 20 EMA crosses above 50 EMA. Sell when 20 EMA crosses below 50 EMA.
Stop loss 2x ATR, take profit 4x ATR. Risk $1,000 per trade. Max 5 trades per day. Max 2% daily loss.
```
**Result**: Compiles, executes, evaluates. Adam killed (negative fitness) as expected.

### ✅ Prompt 2: RSI Mean Reversion (Primary Test)
```
Trade mean reversion on 5-minute bars. Entry: Buy when RSI(14) drops below 30.
Exit: Sell when RSI rises above 70. Stop loss 2x ATR. Take profit 3x ATR.
Position size $1,000 per trade. Risk limits: max 5 trades/day, max 2% daily loss.
```
**Result**: Compiles with correct Constant nodes, executes successfully, transcripts saved.
**Run ID**: 20260130_062402
**Outcome**: Adam killed (fitness=-1.078), negative_fitness

### ✅ Prompt 3: Simple Fixed Stops
```
Buy when RSI(14) drops below 30. Sell when RSI rises above 70.
Stop loss $2. Take profit $5. Position size $1,000 per trade. Max 5 trades/day.
```
**Result**: Compiles, executes successfully.

---

## Commands to Reproduce

### 1. Install dependencies
```bash
python -m pip install -r requirements.txt
cd frontend && npm install && cd ..
```

### 2. Verify baseline
```bash
python demo_validate.py
python demo_evaluate.py
```

### 3. Start services
```bash
# Terminal 1: Backend
cd backend_api
python main.py

# Terminal 2: Frontend
cd frontend
npm run dev
```

### 4. Trigger run via API
```bash
curl -X POST http://localhost:8050/api/run \
  -H "Content-Type: application/json" \
  -d '{
    "nl_text": "Trade mean reversion on 5-minute bars. Entry: Buy when RSI(14) drops below 30. Exit: Sell when RSI rises above 70. Stop loss 2x ATR. Take profit 3x ATR. Position size $1,000 per trade. Risk limits: max 5 trades/day, max 2% daily loss.",
    "universe_symbols": ["AAPL"],
    "timeframe": "5m",
    "start_date": "2024-10-01",
    "end_date": "2024-12-31",
    "depth": 2,
    "branching": 2,
    "survivors_per_layer": 1,
    "max_total_evals": 10,
    "robust_mode": false
  }'
```

### 5. View in browser
Open `http://localhost:5173` and navigate to the run.

---

## Files Changed

### Core Fixes
1. `llm/compile.py` - Comparison operator normalization in repair + system prompt improvements
2. `backtest/simulator.py` - None-safe risk limit checks + Series ambiguity fix
3. `backend_api/main.py` - run_id passthrough to darwin
4. `evolution/darwin.py` - Compile failure handling
5. `evolution/storage.py` - Added `extra` parameter for error states

### Tests Created
6. `tests/test_operator_normalization.py` - Regression test for comparison operators
7. `tests/test_nodetype_normalization.py` - Regression test for NodeType enum format
8. `tests/test_series_ambiguity_fix.py` - Regression test for pandas Series handling
9. `test_mean_reversion.py` - Integration test for complete run flow

---

## Verification Checklist

- [x] **Baseline**: `demo_validate.py` and `demo_evaluate.py` pass
- [x] **Compilation**: Natural language → StrategyGraph succeeds with normalization
- [x] **Execution**: Graph executor runs without lookahead/type errors
- [x] **Validation**: Fitness scoring and kill decisions work deterministically
- [x] **Evolution**: Multi-generation runs complete (even if Adam dies)
- [x] **Transcripts**: LLM transcripts saved per-run with stage tagging
- [x] **Artifacts**: Run directories always created, even on failure
- [x] **API**: No 404s for normal UI flow, proper defaults returned
- [x] **UI**: Frontend loads runs, shows lineage, displays eval/fingerprint/transcripts
- [x] **Error Handling**: Failures logged, artifacts saved, visible in UI

---

## Known Remaining Issues

### Non-Critical
1. **Fast Runs**: When Adam dies immediately (rescue_mode=False), evolution ends after 1 eval. This is by design, not a bug. Users can enable rescue_mode or improve fitness thresholds in Phase 3.

2. **LLM Creativity**: LLMs sometimes generate overly complex strategies with many Constant nodes. Not a bug - normalizations handle this correctly. Can be improved with better prompting in Phase 3.

3. **Cache Hits**: Most LLM calls are cached from previous runs. Expected behavior - speeds up development. Budget.json reflects actual vs cached calls correctly.

### None Critical Enough to Block
All critical bugs that cause **plumbing/graph/IO failures** have been fixed. Remaining work is evolution-policy improvements (Phase 3).

---

## Next Steps (Future Phases)

### Phase 3: Evolution Policy
- Implement grace period for initial strategies
- Add pressure ramping (start lenient, increase strictness)
- Tune fitness thresholds based on actual data distribution
- Add more robust mutation strategies

### Phase 4: Advanced Features
- Graph editing UI (drag-drop nodes)
- Multi-timeframe testing
- Walk-forward analysis
- Live trading integration

---

## Success Criteria Met

✅ Fresh user can start backend + frontend
✅ Trigger run from UI or curl
✅ Watch SSE events in RunDetail
✅ See lineage tree render (when multi-gen runs succeed)
✅ Click nodes and see StrategyInspector populate
✅ See telemetry load without 404s
✅ Confirm LLM calls with transcripts saved
✅ Runs don't die due to plumbing/graph/IO bugs
✅ Errors are deterministic, logged, and visible in UI

---

## Conclusion

**Phase 2 hardening is complete.** The system now runs end-to-end with proper error handling, artifact persistence, and observability. All critical runtime bugs have been resolved. The foundation is solid for Phase 3 evolution-policy improvements.

**Recommendation**: Proceed to Phase 3 when ready to tune selection logic, fitness thresholds, and mutation strategies.
