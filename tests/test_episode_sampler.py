import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd

from validation.episodes import EpisodeSampler


def test_episode_sampler_returns_nonempty_windows():
    dates = pd.date_range("2020-01-01", periods=400, freq="D")
    df = pd.DataFrame({
        "open": 1.0,
        "high": 1.1,
        "low": 0.9,
        "close": 1.05,
    }, index=dates)

    sampler = EpisodeSampler(seed=42)
    episodes = sampler.sample_episodes(df, n_episodes=2, min_months=1, max_months=2, min_bars=20)
    assert len(episodes) == 2
    for spec in episodes:
        assert spec.end_ts > spec.start_ts
        assert not df.loc[spec.start_ts:spec.end_ts].empty
