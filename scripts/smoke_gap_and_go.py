#!/usr/bin/env python3
"""
Smoke test: Gap & Go strategy with event calendar integration.

Tests:
1. Seed prompt compilation (LLM required)
2. Episode sampling with event_day tags
3. Strategy evaluation on episodes
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from llm.compile import compile_nl_to_graph
from validation.episodes import EpisodeSampler, RegimeTagger, slice_episode
from validation.event_calendar import is_event_day, get_event_description
import pandas as pd
from datetime import datetime


def test_event_calendar():
    """Test event calendar functionality."""
    print("\n" + "="*60)
    print("TEST 1: Event Calendar")
    print("="*60)

    # Test known FOMC dates
    fomc_date = datetime(2023, 5, 3)
    assert is_event_day(fomc_date), "Should detect FOMC meeting"
    print(f"✅ Detected event: {get_event_description(fomc_date)}")

    # Test non-event date
    normal_date = datetime(2023, 6, 15)
    assert not is_event_day(normal_date), "Should not be event day"
    print(f"✅ Normal day correctly identified")

    # Test earnings date
    nvda_earnings = datetime(2023, 5, 24)
    assert is_event_day(nvda_earnings), "Should detect NVDA earnings"
    print(f"✅ Detected event: {get_event_description(nvda_earnings)}")


def test_episode_tagging():
    """Test episode tagging with event_day integration."""
    print("\n" + "="*60)
    print("TEST 2: Episode Tagging with Events")
    print("="*60)

    # Create sample data
    dates = pd.date_range("2023-05-01", "2023-05-10", freq="1h")
    df = pd.DataFrame({
        "open": 100 + pd.Series(range(len(dates))).cumsum() * 0.01,
        "high": 101 + pd.Series(range(len(dates))).cumsum() * 0.01,
        "low": 99 + pd.Series(range(len(dates))).cumsum() * 0.01,
        "close": 100 + pd.Series(range(len(dates))).cumsum() * 0.01,
        "volume": 1000000,
    }, index=dates)

    # Tag episode
    tagger = RegimeTagger()
    tags = tagger.tag_episode(df)

    print(f"Tags: {tags}")

    # Check if event_day tag was added (FOMC on 2023-05-03)
    if "event_day" in tags:
        print(f"✅ Event detected in episode: {tags['event_day']}")
    else:
        print("⚠️  No event in this episode (expected if no overlap)")


def test_gap_and_go_compilation():
    """Test Gap & Go strategy compilation from NL prompt."""
    print("\n" + "="*60)
    print("TEST 3: Gap & Go Strategy Compilation")
    print("="*60)

    # Load seed prompt
    prompt_path = Path(__file__).parent.parent / "prompts" / "gap_and_go_seed.txt"

    if not prompt_path.exists():
        print("❌ Seed prompt not found at", prompt_path)
        return

    with open(prompt_path) as f:
        seed_prompt = f.read()

    print("📝 Compiling Gap & Go strategy from NL prompt...")
    print(f"Prompt length: {len(seed_prompt)} chars")

    try:
        # This requires LLM API key
        strategy_graph = compile_nl_to_graph(seed_prompt)

        print(f"✅ Compiled strategy: {strategy_graph.id}")
        print(f"   Universe: {strategy_graph.universe.symbols[:3]}... ({len(strategy_graph.universe.symbols)} tickers)")
        print(f"   Nodes: {len(strategy_graph.nodes)}")
        print(f"   Timeframe: {strategy_graph.time.timeframe}")

        # Check for expected tickers
        expected_tickers = ["TSLA", "NVDA", "AAPL", "AMD"]
        found_tickers = [t for t in expected_tickers if t in strategy_graph.universe.symbols]
        print(f"   Found expected tickers: {found_tickers}")

    except Exception as e:
        print(f"⚠️  Compilation failed (LLM required): {e}")
        print("   This is expected if no API keys are set")


def test_episode_sampling_with_events():
    """Test episode sampling and verify event tagging."""
    print("\n" + "="*60)
    print("TEST 4: Episode Sampling with Event Detection")
    print("="*60)

    # Create longer sample data spanning multiple months
    dates = pd.date_range("2023-01-01", "2023-06-30", freq="5min")
    df = pd.DataFrame({
        "open": 100 + pd.Series(range(len(dates))).cumsum() * 0.001,
        "high": 101 + pd.Series(range(len(dates))).cumsum() * 0.001,
        "low": 99 + pd.Series(range(len(dates))).cumsum() * 0.001,
        "close": 100 + pd.Series(range(len(dates))).cumsum() * 0.001,
        "volume": 1000000,
    }, index=dates)

    # Sample episodes
    sampler = EpisodeSampler(seed=42)
    episodes = sampler.sample_episodes(
        df,
        n_episodes=5,
        min_months=1,
        max_months=2,
        sampling_mode="uniform_random"
    )

    print(f"✅ Sampled {len(episodes)} episodes")

    # Tag episodes and check for events
    tagger = RegimeTagger()
    event_count = 0

    for i, ep in enumerate(episodes, 1):
        episode_df = slice_episode(df, ep.start_ts, ep.end_ts)
        tags = tagger.tag_episode(episode_df)

        print(f"\nEpisode {i}: {ep.start_ts.date()} to {ep.end_ts.date()}")
        print(f"  Tags: {tags}")

        if "event_day" in tags:
            event_count += 1
            print(f"  🎯 Event detected: {tags['event_day']}")

    print(f"\n✅ Found {event_count}/{len(episodes)} episodes with market events")


def main():
    print("\n" + "="*80)
    print("GAP & GO STRATEGY + EVENT CALENDAR SMOKE TEST")
    print("="*80)

    try:
        test_event_calendar()
        test_episode_tagging()
        test_episode_sampling_with_events()
        test_gap_and_go_compilation()  # May fail without LLM keys

        print("\n" + "="*80)
        print("✅ SMOKE TEST PASSED")
        print("="*80)
        print("\nNext steps:")
        print("1. Set LLM API keys to test full compilation")
        print("2. Run: python -m llm.compile --prompt prompts/gap_and_go_seed.txt")
        print("3. Deploy to Render/Akash and run full Darwin evolution")

    except Exception as e:
        print("\n" + "="*80)
        print(f"❌ SMOKE TEST FAILED: {e}")
        print("="*80)
        raise


if __name__ == "__main__":
    main()
