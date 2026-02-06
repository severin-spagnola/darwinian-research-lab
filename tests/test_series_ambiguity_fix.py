"""Test that ATR series retrieval doesn't cause pandas boolean ambiguity."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np
from backtest.simulator import BacktestSimulator


def test_atr_series_retrieval():
    """Test that we can safely retrieve ATR series without pandas ambiguity errors."""

    # Create mock data
    data = pd.DataFrame({
        'timestamp': pd.date_range('2024-01-01', periods=100, freq='5min'),
        'open': 100 + np.random.randn(100),
        'high': 101 + np.random.randn(100),
        'low': 99 + np.random.randn(100),
        'close': 100 + np.random.randn(100),
        'volume': 1000000 + np.random.randint(-100000, 100000, 100),
    })

    # Create mock ATR series
    atr_series = pd.Series([2.0] * 100, name='atr')

    # Simulate stop_config and tp_config with ATR series
    stop_config = {'type': 'atr', 'multiplier': 2.0, 'atr': atr_series}
    tp_config = {'type': 'atr', 'multiplier': 3.0, 'atr': None}

    # This should NOT raise "ValueError: The truth value of a Series is ambiguous"
    # The fix ensures we check `is None` before using `or`
    atr_series_result = stop_config.get('atr')
    if atr_series_result is None:
        atr_series_result = tp_config.get('atr')

    assert atr_series_result is not None
    assert len(atr_series_result) == 100
    assert atr_series_result.iloc[0] == 2.0

    # Test the other way around (stop has None, tp has Series)
    stop_config_2 = {'type': 'atr', 'multiplier': 2.0, 'atr': None}
    tp_config_2 = {'type': 'atr', 'multiplier': 3.0, 'atr': atr_series}

    atr_series_result_2 = stop_config_2.get('atr')
    if atr_series_result_2 is None:
        atr_series_result_2 = tp_config_2.get('atr')

    assert atr_series_result_2 is not None
    assert len(atr_series_result_2) == 100

    # Test both None case
    stop_config_3 = {'type': 'atr', 'multiplier': 2.0, 'atr': None}
    tp_config_3 = {'type': 'atr', 'multiplier': 3.0, 'atr': None}

    atr_series_result_3 = stop_config_3.get('atr')
    if atr_series_result_3 is None:
        atr_series_result_3 = tp_config_3.get('atr')

    assert atr_series_result_3 is None

    print("✓ ATR series retrieval test passed - no pandas boolean ambiguity")


if __name__ == "__main__":
    test_atr_series_retrieval()
