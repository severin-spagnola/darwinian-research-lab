# Phase 3 Part 2 - Production-Ready Episode Evaluation

**Date:** 2026-02-06
**Status:** Complete
**Scope:** Backend only (no frontend changes)

---

## What Shipped

### A) Episode Sampling Enhancements

Four sampling modes are now supported via `Phase3Config.sampling_mode`:

| Mode | Behaviour |
|------|-----------|
| `random` | Original random episode sampling (default) |
| `uniform_random` | Divides date span into equal segments, samples one episode per segment |
| `stratified_by_year` | Distributes episodes proportionally across calendar years |
| `stratified_by_regime` | Over-samples candidates, then selects for regime diversity |

Each `EpisodeSpec` now carries an optional `difficulty: float` score (0.0=easy, 1.0=hard) computed from regime tags.

### B) Regime Tagger Improvements

- Added `drawdown_state` tag: `in_drawdown` (>10% dd), `recovering` (3-10%), `at_highs` (<3%)
- All tagging is **forward-only** - no future data leakage guaranteed
- Comprehensive docstring documents every regime definition and threshold

### C) Robust Fitness Penalties

- **Lucky spike penalty** (`LUCKY_SPIKE_PENALTY=0.2`): Triggered when the single best episode accounts for >60% of total positive fitness. Catches strategies that look good only because of one lucky window.
- **Years covered** tracking: `regime_coverage` now includes `years_covered` list for temporal diversity monitoring.
- Aggregation formula: `median - (worst_case + dispersion + single_regime + lucky_spike)`

### D) Darwin Integration - Curriculum

- `Phase3Config.sampling_mode_schedule: Optional[List[str]]` enables per-generation sampling mode changes (curriculum learning).
  - Example: `["random", "uniform_random", "stratified_by_regime"]` starts easy, gets harder.
- `Phase3Config.get_sampling_mode(generation)` resolves the effective mode.
- `evaluate_strategy_phase3()` accepts `generation` parameter, passed through from Darwin.

### E) Run Artifacts

- New `phase3_reports/` directory under each run: `results/runs/<run_id>/phase3_reports/<graph_id>.json`
- Each report includes: `graph_id`, `fitness`, `decision`, `kill_reason`, `phase3` sub-dict with all episode data, penalties, explanation.
- `RunStorage.save_phase3_report()` is called after every Phase 3 evaluation in Darwin.
- No-ops gracefully when result doesn't contain Phase 3 data.

### F) Backend API

New endpoint:

```
GET /api/runs/{runId}/phase3/{graphId}
```

Returns the Phase 3 report JSON for a specific graph. 404 if not found.

### G) Tests

22 new tests in `tests/test_phase3_part2.py`:

| Test Class | Count | What it covers |
|------------|-------|----------------|
| `TestDeterminism` | 3 | Same seed => same episodes for random, uniform_random, stratified_by_year |
| `TestYearCoverage` | 1 | stratified_by_year picks episodes from >=2 years |
| `TestRegimeCoverage` | 2 | Tagger returns all 4 tags; single-regime penalty fires |
| `TestLuckySpikePenalty` | 4 | Spike triggers/doesn't trigger for various fitness distributions |
| `TestDifficulty` | 3 | Easy vs hard regimes, bounded 0-1 |
| `TestCurriculum` | 2 | get_sampling_mode with/without schedule |
| `TestPhase3ReportStorage` | 2 | Save/load reports; no-op without phase3 data |
| `TestDrawdownTagger` | 2 | at_highs and in_drawdown detection |
| `TestUniformRandom` | 2 | Correct count and temporal coverage |
| `TestPhase3Curriculum` | 1 | Generation-aware sampling mode selection |

**Total test suite: 47 passing** (excluding pre-existing `test_survivor_floor` which requires live LLM)

---

## Files Changed

| File | Change |
|------|--------|
| `validation/episodes.py` | New sampling modes, drawdown tag, difficulty score, documented regime defs |
| `validation/robust_fitness.py` | Lucky spike penalty, years_covered tracking |
| `validation/evaluation.py` | Curriculum support (sampling_mode_schedule, get_sampling_mode), generation param, explanation builder |
| `evolution/darwin.py` | Pass generation to phase3 eval, save phase3 reports |
| `evolution/storage.py` | `save_phase3_report()` method, `phase3_reports/` directory |
| `backend_api/main.py` | `GET /api/runs/{runId}/phase3/{graphId}` endpoint |
| `tests/test_phase3_part2.py` | 22 new tests |
| `scripts/smoke_phase3_darwin.py` | Darwin integration smoke test |

## Backwards Compatibility

- All existing APIs and payloads are unchanged
- `Phase3Config` new fields have defaults (no breaking changes)
- `sampling_mode_schedule` defaults to `None` (uses `sampling_mode` as before)
- `evaluate_strategy_phase3()` new `generation` param defaults to `0`

## Smoke Test

```bash
python scripts/smoke_phase3_darwin.py
```

Verifies: run_config serialization, phase3_report artifacts, eval persistence, summary creation. Passes 4/4 checks without LLM keys.

## Architecture Decisions

1. **Simple heuristics over ML** - Regime tagging uses fixed thresholds (3% trend, ATR ratios, 40% chop ratio, 10%/3% drawdown). Easy to understand and debug.
2. **Forward-only guarantee** - RegimeTagger only uses bars within the episode + trailing history before episode start. Zero lookahead.
3. **Curriculum via schedule lists** - Per-generation overrides use simple index-into-list pattern, same as penalty/holdout schedules. Last element repeats for later generations.
4. **Phase3Report as separate artifact** - Stored alongside evals but in its own directory for clean API access and frontend rendering.
