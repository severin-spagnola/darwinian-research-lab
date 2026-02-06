#!/usr/bin/env python3
"""Create a Darwin run using the Gap & Go strategy for demo."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from evolution.darwin import run_darwin
from validation.evaluation import Phase3Config
from graph.schema import UniverseSpec, TimeConfig, DateRange
from datetime import datetime

# Load Gap & Go seed prompt
prompt_path = Path(__file__).parent.parent / "prompts" / "gap_and_go_seed.txt"
with open(prompt_path) as f:
    seed_prompt = f.read()

# Universe (intraday stocks)
universe = UniverseSpec(type="explicit", symbols=["TSLA", "NVDA", "AAPL", "AMD", "COIN"])

# Time config for intraday strategy
time_config = TimeConfig(
    timeframe="5min",  # 5-minute bars for gap-and-go
    lookback_days=90,  # 3 months of data
    date_range=DateRange(
        start=datetime(2024, 10, 1),  # Recent data
        end=datetime(2025, 1, 31)
    )
)

# Phase 3 with event tagging
phase3_config = Phase3Config(
    n_episodes=5,  # 5 episodes for diversity
    min_months=1,
    max_months=2,
    sampling_mode="uniform_random"  # Spread across time range
)

print("🚀 Creating Gap & Go Darwin run...")
print(f"   Universe: {universe.symbols}")
print(f"   Timeframe: {time_config.timeframe}")
print(f"   Date Range: {time_config.date_range.start.date()} to {time_config.date_range.end.date()}")
print(f"   Phase 3: {phase3_config.n_episodes} episodes with event tagging")
print("\n⚠️  This requires:")
print("   - LLM API key (OpenAI or Anthropic)")
print("   - Polygon API key")
print("\n⏱️  Estimated time: 10-15 minutes for 2 generations")
print("\nStarting evolution...\n")

try:
    run_summary = run_darwin(
        seed_prompt=seed_prompt,
        universe=universe,
        time_config=time_config,
        generations=2,  # Small number for demo
        survivors_per_gen=3,
        children_per_survivor=2,
        phase3_config=phase3_config
    )

    print("\n" + "="*60)
    print("✅ GAP & GO RUN CREATED!")
    print("="*60)
    print(f"Run ID: {run_summary['run_id']}")
    print(f"Generations: {run_summary.get('total_generations', 2)}")
    print(f"Strategies Evaluated: {run_summary.get('total_evaluated', 'N/A')}")
    print(f"\n🌐 View in frontend:")
    print(f"   https://your-vercel-url.vercel.app")
    print(f"\n📊 Results saved to:")
    print(f"   results/runs/{run_summary['run_id']}/")
    print("\nRefresh your frontend to see real data!")

except Exception as e:
    print("\n" + "="*60)
    print("❌ FAILED TO CREATE RUN")
    print("="*60)
    print(f"Error: {e}")
    print("\nTroubleshooting:")
    print("  1. Check API keys are set:")
    print("     - OPENAI_API_KEY or ANTHROPIC_API_KEY")
    print("     - POLYGON_API_KEY")
    print("  2. Verify internet connection")
    print("  3. Check Polygon API limits (5 requests/min on free tier)")
    print("\nFor demo purposes, you can use mock data in the frontend.")
    import traceback
    traceback.print_exc()
