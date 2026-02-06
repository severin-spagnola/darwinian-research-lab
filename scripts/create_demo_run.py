#!/usr/bin/env python3
"""Create a quick demo Darwin run for frontend testing."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from evolution.darwin import run_darwin
from validation.evaluation import Phase3Config
from graph.schema import UniverseSpec, TimeConfig, DateRange
from datetime import datetime

# Simple configuration for quick demo
universe = UniverseSpec(type="explicit", symbols=["AAPL", "TSLA", "NVDA"])
time_config = TimeConfig(
    timeframe="1d",
    lookback_days=365,
    date_range=DateRange(
        start=datetime(2023, 1, 1),
        end=datetime(2023, 12, 31)
    )
)

# Phase 3 config with event tagging
phase3_config = Phase3Config(
    n_episodes=3,  # Small number for quick demo
    min_months=2,
    max_months=4,
    sampling_mode="uniform_random"
)

# Seed prompt
seed_prompt = """
Create a simple momentum strategy:
- Buy when RSI(14) > 60 (momentum building)
- Sell when RSI(14) < 40 (momentum fading)
- Use 5-day moving average as trend filter
"""

print("🚀 Creating demo Darwin run...")
print(f"   Universe: {universe.symbols}")
print(f"   Timeframe: {time_config.timeframe}")
print(f"   Phase 3: {phase3_config.n_episodes} episodes")
print("\nThis will take 5-10 minutes with LLM API keys...")

try:
    run_summary = run_darwin(
        seed_prompt=seed_prompt,
        universe=universe,
        time_config=time_config,
        generations=2,  # Just 2 generations for demo
        survivors_per_gen=2,
        children_per_survivor=2,
        phase3_config=phase3_config
    )

    print("\n✅ Demo run created!")
    print(f"   Run ID: {run_summary['run_id']}")
    print(f"   Check frontend: Your Vercel URL")

except Exception as e:
    print(f"\n❌ Failed to create run: {e}")
    print("\nMake sure you have:")
    print("  - OPENAI_API_KEY or ANTHROPIC_API_KEY set")
    print("  - POLYGON_API_KEY set")
    print("  - Internet connection")
