#!/usr/bin/env python3
"""Create a Darwin run using the Gap & Go strategy for demo."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from evolution.darwin import run_darwin
from validation.evaluation import Phase3Config
from graph.schema import UniverseSpec, TimeConfig, DateRange
from data.polygon_client import PolygonClient

# Load Gap & Go seed prompt
prompt_path = Path(__file__).parent.parent / "prompts" / "gap_and_go_seed.txt"
with open(prompt_path) as f:
    seed_prompt = f.read()

# Universe (intraday stocks)
universe = UniverseSpec(type="explicit", symbols=["TSLA", "NVDA", "AAPL", "AMD", "COIN"])

# Time config for intraday strategy
time_config = TimeConfig(
    timeframe="5m",
    lookback_days=90,
    date_range=DateRange(start="2024-10-01", end="2025-01-31")
)

# Phase 3 with event tagging
phase3_config = Phase3Config(
    n_episodes=5,
    min_months=1,
    max_months=2,
    sampling_mode="uniform_random"
)

print("🚀 Creating Gap & Go Darwin run...")
print(f"   Universe: {universe.symbols}")
print(f"   Timeframe: {time_config.timeframe}")
print(f"   Date Range: {time_config.date_range.start} to {time_config.date_range.end}")
print(f"   Phase 3: {phase3_config.n_episodes} episodes with event tagging")
print("\nFetching market data from Polygon...")

# Fetch data first (run_darwin expects a DataFrame)
client = PolygonClient()
dr = time_config.date_range
data = None
for sym in universe.symbols:
    try:
        df = client.get_bars(symbol=sym, timeframe=time_config.timeframe, start=dr.start, end=dr.end)
        if df is not None and not df.empty:
            if data is None:
                data = df
                print(f"   ✅ {sym}: {len(df)} bars")
            else:
                print(f"   ⏭️  {sym}: skipped (using first symbol)")
    except Exception as e:
        print(f"   ❌ {sym}: {e}")

if data is None:
    print("❌ No data fetched. Check POLYGON_API_KEY.")
    sys.exit(1)

print(f"\nStarting evolution with {len(data)} bars...\n")

try:
    run_summary = run_darwin(
        data=data,
        universe=universe,
        time_config=time_config,
        nl_text=seed_prompt,
        depth=2,
        branching=2,
        survivors_per_layer=3,
        phase3_config=phase3_config,
        rescue_mode=True,
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
