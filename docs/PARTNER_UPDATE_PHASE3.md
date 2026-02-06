# Phase 3 Partner Update (Backend)

## What Changed

### Phase 3.1 — Episode-Based Robustness Evaluation
Strategies are now evaluated across multiple random time windows ("episodes") instead of a single train/holdout split. Each episode is tagged with a market regime (trend, volatility, choppiness). Fitness is aggregated as median across episodes minus penalties for worst-case, dispersion, and single-regime dependence.

### Phase 3.2 — Adaptive Selection Pressure + Grace Period
Early generations now get a "grace period" where killed strategies are softened to `mutate_only` instead of hard-killed. This prevents Adam from dying instantly. Penalty weights and holdout trade requirements ramp up over generations.

## API / Endpoint Changes
- **No new endpoints added.**
- **No existing endpoint signatures changed.**

## Payload Shape Changes
`run_config.json` now includes an optional `phase3_config` block when Phase 3 is enabled:
```json
{
  "phase3_config": {
    "enabled": true,
    "mode": "episodes",
    "n_episodes": 8,
    "schedule": {
      "grace_generations": 1,
      "penalty_weight_schedule": [0.0, 0.5, 1.0],
      "min_holdout_trades_schedule": [0, 3, 10]
    }
  }
}
```
This block is absent when Phase 3 is disabled (backward-compatible).

## New Fields in Evaluation Results
When Phase 3 is active, `validation_report` contains a `phase3` key:
| Field | Type | Meaning |
|-------|------|---------|
| `aggregated_fitness` | float | Final fitness (median - penalties) |
| `median_fitness` | float | Median across episodes |
| `worst_fitness` / `best_fitness` | float | Extremes |
| `worst_case_penalty` | float | 0.5 if any episode < -0.5 |
| `dispersion_penalty` | float | 0.25 if std > 0.3 |
| `single_regime_penalty` | float | 0.3 if single-regime dependent |
| `regime_coverage.unique_regimes` | int | Distinct regime combos seen |
| `episodes[].tags` | dict | `{trend, vol_bucket, chop_bucket}` |
| `episodes[].fitness` | float | Per-episode fitness |
| `n_trades_per_episode` | list[int] | Trade counts per episode |

A new `decision` value `"mutate_only"` may appear during grace period (treat same as `"kill"` for display but lineage continues).

## How to Interpret
- **Positive aggregated fitness + decision=survive**: strategy is robust.
- **Negative aggregated fitness**: strategy fails across regimes.
- **High dispersion**: inconsistent performance, likely overfit to one regime.
- **mutate_only**: strategy failed but was in grace period; mutations will continue.
