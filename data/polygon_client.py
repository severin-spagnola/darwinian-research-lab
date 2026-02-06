import requests
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
import hashlib
import json
from typing import Dict, List
from config import POLYGON_API_KEY, CACHE_DIR, CACHE_EXPIRY_DAYS


class PolygonClient:
    BASE_URL = "https://api.polygon.io/v2/aggs/ticker"
    
    def __init__(self, api_key: str = POLYGON_API_KEY):
        if not api_key:
            raise ValueError("POLYGON_API_KEY not set")
        self.api_key = api_key
        self.cache_dir = CACHE_DIR
        
    def _get_cache_path(self, symbol: str, timeframe: str, start: str, end: str) -> Path:
        """Generate cache file path based on request params."""
        cache_key = f"{symbol}_{timeframe}_{start}_{end}"
        hash_key = hashlib.md5(cache_key.encode()).hexdigest()
        return self.cache_dir / f"{hash_key}.parquet"
    
    def _is_cache_valid(self, cache_path: Path) -> bool:
        """Check if cache file exists and is not expired."""
        if not cache_path.exists():
            return False
        
        mtime = datetime.fromtimestamp(cache_path.stat().st_mtime)
        age = datetime.now() - mtime
        return age < timedelta(days=CACHE_EXPIRY_DAYS)
    
    def _load_from_cache(self, cache_path: Path) -> pd.DataFrame:
        """Load DataFrame from cache."""
        return pd.read_parquet(cache_path)
    
    def _save_to_cache(self, df: pd.DataFrame, cache_path: Path):
        """Save DataFrame to cache."""
        df.to_parquet(cache_path, index=False)
    
    def _fetch_from_polygon(self, symbol: str, timeframe: str, start: str, end: str) -> pd.DataFrame:
        """Fetch bars from Polygon API."""
        # Convert timeframe to Polygon format
        # "5m" -> multiplier=5, timespan="minute"
        # "1h" -> multiplier=1, timespan="hour"
        # "1d" -> multiplier=1, timespan="day"
        
        if timeframe.endswith('m'):
            multiplier = int(timeframe[:-1])
            timespan = "minute"
        elif timeframe.endswith('h'):
            multiplier = int(timeframe[:-1])
            timespan = "hour"
        elif timeframe.endswith('d'):
            multiplier = int(timeframe[:-1])
            timespan = "day"
        else:
            raise ValueError(f"Invalid timeframe: {timeframe}")
        
        url = f"{self.BASE_URL}/{symbol}/range/{multiplier}/{timespan}/{start}/{end}"
        params = {
            "apiKey": self.api_key,
            "adjusted": "true",
            "sort": "asc",
            "limit": 50000
        }
        
        all_results = []
        
        while True:
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            if data.get("status") != "OK":
                raise ValueError(f"Polygon API error: {data.get('error', 'Unknown error')}")
            
            results = data.get("results", [])
            if not results:
                break
                
            all_results.extend(results)
            
            # Check for pagination
            next_url = data.get("next_url")
            if not next_url:
                break
            
            url = next_url
            params = {"apiKey": self.api_key}  # next_url already has other params
        
        if not all_results:
            return pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        
        # Convert to DataFrame
        df = pd.DataFrame(all_results)
        df = df.rename(columns={
            't': 'timestamp',
            'o': 'open',
            'h': 'high',
            'l': 'low',
            'c': 'close',
            'v': 'volume'
        })
        
        # Convert timestamp from ms to datetime (UTC)
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
        
        # Select and order columns
        df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
        
        return df
    
    def get_bars(self, symbol: str, timeframe: str, start: str, end: str) -> pd.DataFrame:
        """
        Get OHLCV bars for a single symbol.
        
        Args:
            symbol: Ticker symbol (e.g., "AAPL")
            timeframe: Bar size (e.g., "5m", "1h", "1d")
            start: Start date (YYYY-MM-DD)
            end: End date (YYYY-MM-DD)
            
        Returns:
            DataFrame with columns: timestamp, open, high, low, close, volume
        """
        cache_path = self._get_cache_path(symbol, timeframe, start, end)
        
        if self._is_cache_valid(cache_path):
            print(f"Loading {symbol} {timeframe} from cache...")
            return self._load_from_cache(cache_path)
        
        print(f"Fetching {symbol} {timeframe} from Polygon...")
        df = self._fetch_from_polygon(symbol, timeframe, start, end)
        
        if not df.empty:
            self._save_to_cache(df, cache_path)
        
        return df


def get_bars(symbols: List[str], timeframe: str, start: str, end: str) -> Dict[str, pd.DataFrame]:
    """
    Get OHLCV bars for multiple symbols.
    
    Args:
        symbols: List of ticker symbols
        timeframe: Bar size (e.g., "5m", "1h", "1d")
        start: Start date (YYYY-MM-DD)
        end: End date (YYYY-MM-DD)
        
    Returns:
        Dictionary mapping symbol -> DataFrame
    """
    client = PolygonClient()
    result = {}
    
    for symbol in symbols:
        try:
            result[symbol] = client.get_bars(symbol, timeframe, start, end)
        except Exception as e:
            print(f"Error fetching {symbol}: {e}")
            result[symbol] = pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    
    return result