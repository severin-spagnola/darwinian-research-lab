#!/usr/bin/env python3
"""
Phase 3 Part 2 Darwin Evolution Experiment

Research experiment to validate Phase 3 stratified sampling and regime robustness
selection pressure in a real evolutionary run.
"""

import json
from pathlib import Path
from datetime import datetime

from data.polygon_client import PolygonClient
from graph.schema import UniverseSpec, TimeConfig, DateRange
from validation.evaluation import Phase3Config
from evolution.darwin import run_darwin

print("="*80)
print("PHASE 3 PART 2 DARWIN EVOLUTION EXPERIMENT")
print("="*80)

# Experimental parameters
EXPERIMENT_CONFIG = {
    "run_seed": 42,
    "population_size": 10,
    "n_generations": 5,
    "survivors_per_gen": 3,
    "phase3_enabled": True,
    "phase3_mode": "episodes",
    "sampling_mode": "stratified_by_regime",
    "n_episodes": 6,
    "min_months": 1,
    "max_months": 2,
    "seed": 42,
}

print("\n[EXPERIMENTAL SETUP]")
print(f"Run Seed: {EXPERIMENT_CONFIG['run_seed']}")
print(f"Population: {EXPERIMENT_CONFIG['population_size']} strategies per generation")
print(f"Generations: {EXPERIMENT_CONFIG['n_generations']}")
print(f"Survivors: {EXPERIMENT_CONFIG['survivors_per_gen']} per generation")
print(f"Phase 3 Mode: {EXPERIMENT_CONFIG['sampling_mode']}")
print(f"Episodes per evaluation: {EXPERIMENT_CONFIG['n_episodes']}")

# Load data
print("\n[DATA LOADING]")
client = PolygonClient()
data = client.get_bars("AAPL", "5m", "2024-10-01", "2024-12-31")
print(f"Loaded {len(data)} bars of AAPL 5m data")
print(f"Date range: {data['timestamp'].min()} to {data['timestamp'].max()}")

# Set timestamp as index for Phase 3
if 'timestamp' in data.columns:
    data = data.set_index('timestamp')
    print("Set timestamp as index for Phase 3 evaluation")

# Configure Phase 3
phase3_config = Phase3Config(
    enabled=EXPERIMENT_CONFIG["phase3_enabled"],
    mode=EXPERIMENT_CONFIG["phase3_mode"],
    n_episodes=EXPERIMENT_CONFIG["n_episodes"],
    min_months=EXPERIMENT_CONFIG["min_months"],
    max_months=EXPERIMENT_CONFIG["max_months"],
    min_bars=50,
    seed=EXPERIMENT_CONFIG["seed"],
    sampling_mode=EXPERIMENT_CONFIG["sampling_mode"],
    min_trades_per_episode=2,
    regime_penalty_weight=0.3,
    abort_on_all_episode_failures=False,  # Don't abort during evolution
)

print(f"\n[PHASE 3 CONFIG]")
print(f"Enabled: {phase3_config.enabled}")
print(f"Mode: {phase3_config.mode}")
print(f"Sampling: {phase3_config.sampling_mode}")
print(f"Episodes: {phase3_config.n_episodes}")
print(f"Regime penalty weight: {phase3_config.regime_penalty_weight}")

# Universe and time config
universe = UniverseSpec(type="explicit", symbols=["AAPL"])
time_config = TimeConfig(
    timeframe="5m",
    date_range=DateRange(start="2024-10-01", end="2024-12-31"),
)

# Adam strategy prompt (simple momentum strategy that should trade)
adam_prompt = """
Create a simple momentum breakout strategy:
- Enter long when price crosses above 20-period SMA
- Exit when price crosses below 20-period SMA
- Use fixed stop loss at 3 points below entry
- Use fixed take profit at 6 points above entry
- Fixed position size of $3000
- Max 5 trades per day
- Only trade between 10am and 3pm
"""

print(f"\n[ADAM STRATEGY]")
print(f"Natural language prompt:\n{adam_prompt}")

# Run Darwin evolution
print(f"\n{'='*80}")
print("STARTING DARWIN EVOLUTION")
print(f"{'='*80}\n")

result = run_darwin(
    data=data,
    universe=universe,
    time_config=time_config,
    nl_text=adam_prompt,
    depth=EXPERIMENT_CONFIG["n_generations"],
    branching=EXPERIMENT_CONFIG["population_size"],
    survivors_per_layer=EXPERIMENT_CONFIG["survivors_per_gen"],
    phase3_config=phase3_config,
    rescue_mode=True,  # Allow evolution even if Adam is killed
    run_id=f"phase3_exp_{EXPERIMENT_CONFIG['run_seed']}_fixed",
)

print(f"\n{'='*80}")
print("DARWIN EVOLUTION COMPLETE")
print(f"{'='*80}\n")

# Save experiment metadata
experiment_dir = Path("results/experiments/phase3_darwin")
experiment_dir.mkdir(parents=True, exist_ok=True)

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
metadata_path = experiment_dir / f"experiment_{timestamp}_metadata.json"

metadata = {
    "timestamp": timestamp,
    "config": EXPERIMENT_CONFIG,
    "data_summary": {
        "symbol": "AAPL",
        "timeframe": "5m",
        "n_bars": len(data),
        "start": str(data.index.min()),
        "end": str(data.index.max()),
    },
    "adam_prompt": adam_prompt,
    "run_id": result.run_id if hasattr(result, 'run_id') else None,
}

with open(metadata_path, "w") as f:
    json.dump(metadata, f, indent=2)

print(f"\n[ARTIFACTS SAVED]")
print(f"Experiment metadata: {metadata_path}")
print(f"Darwin run artifacts: results/runs/{result.run_id if hasattr(result, 'run_id') else 'unknown'}/")

print(f"\n{'='*80}")
print("EXPERIMENT COMPLETE - See results for detailed analysis")
print(f"{'='*80}")
