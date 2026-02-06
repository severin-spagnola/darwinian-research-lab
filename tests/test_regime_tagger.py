import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd

from validation.episodes import RegimeTagger


def test_trend_detects_flat_and_up_trends():
    # Trending data
    up_dates = pd.date_range("2021-01-01", periods=120, freq="D")
    up_df = pd.DataFrame({
        "open": range(120),
        "high": range(1, 121),
        "low": range(120),
        "close": range(120),
    }, index=up_dates)

    tagger = RegimeTagger()
    tags = tagger.tag_episode(up_df)
    assert tags["trend"] == "up"

    # Flat data
    flat_dates = pd.date_range("2021-01-01", periods=120, freq="D")
    flat_df = pd.DataFrame({
        "open": [1.0] * 120,
        "high": [1.0] * 120,
        "low": [1.0] * 120,
        "close": [1.0] * 120,
    }, index=flat_dates)
    flat_tags = tagger.tag_episode(flat_df)
    assert flat_tags["trend"] == "flat"
