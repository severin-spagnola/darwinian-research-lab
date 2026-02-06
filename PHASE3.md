# Phase 3: Episode-Based Robustness Evaluation

## Overview

Phase 3 implements episode-based robustness evaluation for strategies, moving beyond simple train/holdout splits to test strategy performance across multiple random time windows with different market regimes. This approach provides stronger signals about true out-of-sample performance and prevents strategies from overfitting to specific market conditions.

## Key Concepts

### Episodes
An **episode** is a contiguous time window sampled from the available data. Each episode:
- Has a random start time and duration (e.g., 6-12 months)
- Must contain a minimum number of bars to be valid
- Is tagged with market regime characteristics (trend, volatility, choppiness)
- Represents an independent evaluation of the strategy

### Market Regimes
Each episode is automatically tagged with three regime characteristics:

1. **Trend**: `up`, `down`, or `flat`
   - Based on price change from episode start to end
   - Uses percentage change (>3% threshold) or absolute change for low prices

2. **Volatility Bucket**: `low`, `mid`, or `high`
   - Based on Average True Range (ATR) as percentage of price
   - Normalized against historical volatility when available

3. **Choppiness**: `trending` or `choppy`
   - Ratio of net directional move to total price range
   - Trending if ratio > 0.4 (price moved consistently in one direction)

### Fitness Aggregation
Instead of a single fitness score, Phase 3 computes:
- **Median fitness** across all episodes (base metric)
- **Worst-case penalty** (0.5) if any episode has fitness < -0.5
- **Dispersion penalty** (0.25) if standard deviation > 0.3
- **Single-regime penalty** (configurable weight) if strategy only works in one regime type

## Part 1: Basic Episode Evaluation ✅ COMPLETE

### Features
- Random episode sampling with deterministic seeding
- Regime tagging (trend, volatility, choppiness)
- Per-episode fitness evaluation
- Median-based aggregation with worst-case and dispersion penalties

### Usage

```python
from validation.evaluation import Phase3Config, evaluate_strategy_phase3

# Configure Phase 3 evaluation
config = Phase3Config(
    enabled=True,
    mode="episodes",  # Must be "episodes" to enable Phase 3
    n_episodes=8,     # Number of episodes to sample
    min_months=6,     # Minimum episode duration
    max_months=12,    # Maximum episode duration
    min_bars=120,     # Minimum bars per episode
    seed=42,          # For reproducibility
)

# Evaluate strategy (data must have timestamp as index)
result = evaluate_strategy_phase3(
    strategy=strategy_graph,
    data=dataframe,
    phase3_config=config,
    initial_capital=100000.0,
)

# Access results
print(f"Aggregated fitness: {result.fitness}")
print(f"Decision: {result.decision}")

# Per-episode details in validation_report
phase3_data = result.validation_report["phase3"]
for episode in phase3_data["episodes"]:
    print(f"{episode['label']}: fitness={episode['fitness']}, regime={episode['tags']}")
```

## Part 2: Stratified Sampling & Regime Robustness ✅ COMPLETE

### New Features

#### 1. Stratified Sampling by Regime
Ensures episode coverage across different market regimes instead of purely random selection.

**Algorithm**:
1. Sample 2-3x more candidate episodes than needed
2. Tag each candidate with regime labels
3. Greedily select episodes to maximize unique regime combinations
4. Fall back to random sampling if insufficient diversity

**Benefits**:
- Better tests for regime-dependent overfitting
- More reliable robustness assessment
- Explicit regime coverage metrics

#### 2. Regime Robustness Metrics
Track per-regime performance to identify single-regime dependencies:

- **Unique regimes**: Count of distinct regime combinations observed
- **Regime counts**: Episodes per regime combination
- **Per-regime fitness**: Fitness scores grouped by regime
- **Trades per episode**: Track trading activity across episodes

#### 3. Single-Regime Penalty
Penalizes strategies that only work in one market regime type.

**Penalty Applied If**:
- Only 1 unique regime observed across all episodes, OR
- One regime has 80%+ of positive fitness episodes

**Default Weight**: 0.3 (configurable via `regime_penalty_weight`)

#### 4. Enhanced Phase3Config

```python
from validation.evaluation import Phase3Config

@dataclass
class Phase3Config:
    enabled: bool = False
    mode: str = "baseline"  # "episodes" to enable Phase 3
    n_episodes: int = 8
    min_months: int = 6
    max_months: int = 12
    min_bars: int = 120
    seed: Optional[int] = None

    # Part 2 additions:
    sampling_mode: str = "random"  # "random" or "stratified_by_regime"
    min_trades_per_episode: int = 3  # Minimum trades for valid episode
    regime_penalty_weight: float = 0.3  # Weight for single-regime penalty
```

### Usage Example

```python
from validation.evaluation import Phase3Config, evaluate_strategy_phase3

# Enable stratified sampling and regime penalties
config = Phase3Config(
    enabled=True,
    mode="episodes",
    n_episodes=8,
    min_months=6,
    max_months=12,
    min_bars=120,
    seed=42,
    sampling_mode="stratified_by_regime",  # NEW: stratified sampling
    min_trades_per_episode=3,              # NEW: minimum trade threshold
    regime_penalty_weight=0.3,             # NEW: single-regime penalty weight
)

result = evaluate_strategy_phase3(
    strategy=strategy_graph,
    data=dataframe,
    phase3_config=config,
    initial_capital=100000.0,
)

# Access regime metrics
phase3_data = result.validation_report["phase3"]
print(f"Aggregated fitness: {phase3_data['aggregated_fitness']:.3f}")
print(f"Unique regimes: {phase3_data['regime_coverage']['unique_regimes']}")
print(f"Single-regime penalty: {phase3_data['single_regime_penalty']:.3f}")

# Check regime distribution
for regime_str, count in phase3_data['regime_coverage']['regime_counts'].items():
    print(f"  {regime_str}: {count} episodes")
```

### Validation Report Structure

```json
{
  "phase3": {
    "aggregated_fitness": 0.234,
    "median_fitness": 0.456,
    "worst_fitness": -0.123,
    "best_fitness": 0.789,
    "std_fitness": 0.234,
    "worst_case_penalty": 0.0,
    "dispersion_penalty": 0.0,
    "single_regime_penalty": 0.0,
    "regime_coverage": {
      "unique_regimes": 5,
      "regime_counts": {
        "(('chop_bucket', 'trending'), ('trend', 'up'), ('vol_bucket', 'mid'))": 2,
        "(('chop_bucket', 'choppy'), ('trend', 'down'), ('vol_bucket', 'high'))": 1
      },
      "per_regime_fitness": {
        "(('chop_bucket', 'trending'), ('trend', 'up'), ('vol_bucket', 'mid'))": [0.5, 0.6],
        "(('chop_bucket', 'choppy'), ('trend', 'down'), ('vol_bucket', 'high'))": [-0.1]
      }
    },
    "n_trades_per_episode": [5, 3, 7, 4, 6, 2, 8, 4],
    "episodes": [
      {
        "label": "episode_1",
        "start_ts": "2024-01-15T09:30:00",
        "end_ts": "2024-02-28T16:00:00",
        "fitness": 0.456,
        "decision": "survive",
        "kill_reason": [],
        "tags": {
          "trend": "up",
          "vol_bucket": "mid",
          "chop_bucket": "trending"
        }
      }
    ]
  }
}
```

## Testing

### Run All Phase 3 Tests
```bash
# Part 1 tests
python -m pytest tests/test_episode_sampler.py tests/test_regime_tagger.py tests/test_robust_aggregate.py -v

# Part 2 tests (stratified sampling and regime penalties)
python -m pytest tests/test_stratified_sampling.py -v

# All Phase 3 tests together
python -m pytest tests/test_episode_sampler.py tests/test_regime_tagger.py tests/test_robust_aggregate.py tests/test_stratified_sampling.py -v
```

### Run Demos
```bash
# Part 1: Basic episode evaluation
python demo_phase3_sanity.py

# Part 2: Stratified sampling comparison (random vs stratified)
python demo_phase3_part2.py
```

## Integration with Darwin Evolution

Phase 3 is integrated into the Darwin evolution pipeline via `evaluate_strategy_phase3`. When `phase3_config.enabled=True` and `phase3_config.mode="episodes"`, the evaluation switches from legacy train/holdout to episode-based evaluation.

### Darwin Usage
```python
from evolution.darwin import run_darwin
from validation.evaluation import Phase3Config

result = run_darwin(
    data=data,
    universe=universe_spec,
    time_config=time_config,
    nl_text="Create a momentum strategy",
    depth=3,
    branching=3,
    survivors_per_layer=2,
    phase3_config=Phase3Config(
        enabled=True,
        mode="episodes",
        n_episodes=8,
        sampling_mode="stratified_by_regime",
        regime_penalty_weight=0.3,
    ),
)
```

## Implementation Files

### Core Implementation
- [validation/episodes.py](validation/episodes.py) - Episode sampling and regime tagging
  - `EpisodeSampler` class with random and stratified sampling
  - `RegimeTagger` class for trend/volatility/choppiness detection
  - Lines 100-204: Stratified sampling implementation

- [validation/robust_fitness.py](validation/robust_fitness.py) - Aggregation and penalties
  - `evaluate_strategy_on_episodes()` - Main evaluation loop
  - `_compute_regime_coverage()` - Per-regime statistics
  - `_compute_single_regime_penalty()` - Single-regime penalty logic
  - Lines 120-180: Regime metrics implementation

- [validation/evaluation.py](validation/evaluation.py) - Integration with evaluation pipeline
  - `Phase3Config` dataclass with all knobs
  - `evaluate_strategy_phase3()` - Entry point for Phase 3 evaluation
  - Lines 75-86: Phase3Config definition with Part 2 additions

### Tests
- [tests/test_episode_sampler.py](tests/test_episode_sampler.py) - Episode sampling tests
- [tests/test_regime_tagger.py](tests/test_regime_tagger.py) - Regime tagging tests
- [tests/test_robust_aggregate.py](tests/test_robust_aggregate.py) - Aggregation tests
- [tests/test_stratified_sampling.py](tests/test_stratified_sampling.py) - Part 2 tests
  - Stratified sampling validation
  - Regime coverage computation
  - Single-regime penalty logic
  - Phase3Config knobs

### Demos
- [demo_phase3_sanity.py](demo_phase3_sanity.py) - Part 1 end-to-end demo
- [demo_phase3_part2.py](demo_phase3_part2.py) - Part 2 comparison demo (random vs stratified)

### Documentation
- [PHASE3_PART1_VERIFICATION_REPORT.md](PHASE3_PART1_VERIFICATION_REPORT.md) - Part 1 verification report
- [PHASE3.md](PHASE3.md) - This file

## Design Principles

1. **Deterministic**: All sampling uses explicit seeds for reproducibility
2. **Backward Compatible**: Legacy evaluation still works when Phase 3 disabled
3. **Lightweight Regimes**: Simple heuristics (trend, vol, chop) not ML models
4. **Median-Based**: Robust to outlier episodes
5. **Penalty-Based**: Explicit penalties for overfitting signals
6. **Serializable**: All results stored in JSON-friendly structures
7. **Small Diffs**: Prefer minimal changes to existing code paths

## Penalties Summary

| Penalty Type | Threshold | Weight | When Applied |
|--------------|-----------|--------|--------------|
| Worst-case | Worst fitness < -0.5 | 0.5 | Any episode has very negative fitness |
| Dispersion | Std dev > 0.3 | 0.25 | High variance across episodes |
| Single-regime | 80%+ positive in one regime | 0.3 (configurable) | Strategy works in only one market condition |

**Final Aggregated Fitness** = Median Fitness - (Worst-case + Dispersion + Single-regime penalties)

## Future Enhancements (Not Yet Implemented)

- [ ] Per-regime kill policies (e.g., require survival in at least 2 regimes)
- [ ] Regime-weighted fitness (weight by regime frequency in full dataset)
- [ ] Episode overlap detection and deduplication
- [ ] Custom regime definitions (user-provided regime classifiers)
- [ ] Multi-symbol regime tagging (correlation, sector rotation)
- [ ] Episode difficulty scoring (assign harder episodes more weight)

## Changelog

### Part 1 (Completed)
- ✅ Episode sampling with deterministic seeding
- ✅ Regime tagging (trend, volatility, choppiness)
- ✅ Per-episode evaluation
- ✅ Median-based aggregation
- ✅ Worst-case and dispersion penalties
- ✅ Comprehensive tests and demo
- ✅ Verification report

### Part 2 (Completed)
- ✅ Stratified sampling by regime
- ✅ Regime coverage metrics
- ✅ Single-regime penalty
- ✅ Phase3Config knobs (sampling_mode, min_trades_per_episode, regime_penalty_weight)
- ✅ Per-regime fitness tracking
- ✅ Tests for stratified sampling and regime penalties
- ✅ Comparison demo (random vs stratified)
- ✅ Documentation update

## References

- **Part 1 Verification**: [PHASE3_PART1_VERIFICATION_REPORT.md](PHASE3_PART1_VERIFICATION_REPORT.md)
- **Test Files**: All tests in [tests/](tests/) directory prefixed with `test_episode_`, `test_regime_`, `test_robust_`, `test_stratified_`
- **Demo Scripts**: [demo_phase3_sanity.py](demo_phase3_sanity.py), [demo_phase3_part2.py](demo_phase3_part2.py)
