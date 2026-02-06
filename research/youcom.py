"""You.com research provider integration with persistent caching.

Environment variable required: YOUCOM_API_KEY
"""

import hashlib
import json
import os
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
import requests

from research.models import ResearchSource, ResearchPack, ResearchExtraction
import config


# ============================================================================
# Configuration
# ============================================================================

YOUCOM_API_KEY = os.getenv("YOUCOM_API_KEY", "")
YOUCOM_API_URL = "https://api.ydc-index.io/search"
TIMEOUT_SECONDS = 10
MAX_RETRIES = 2
RETRY_DELAY = 1.0


def _get_cache_dir() -> Path:
    """Get cache directory (resolves dynamically for testing)."""
    cache_dir = config.RESULTS_DIR / "research_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


# ============================================================================
# HTTP Client (mockable for tests)
# ============================================================================

class YouComClient:
    """HTTP client for You.com API (mockable for testing)."""

    def __init__(self, api_key: Optional[str] = None, timeout: float = TIMEOUT_SECONDS):
        self.api_key = api_key or YOUCOM_API_KEY
        self.timeout = timeout

    def search(self, query: str, n_results: int = 5) -> Dict[str, Any]:
        """Execute You.com search query.

        Returns raw API response.

        Raises:
            requests.RequestException: on network/API errors
            ValueError: if API key missing
        """
        if not self.api_key:
            raise ValueError("YOUCOM_API_KEY not set")

        headers = {"X-API-Key": self.api_key}
        params = {"query": query, "num_web_results": n_results}

        for attempt in range(MAX_RETRIES + 1):
            try:
                response = requests.get(
                    YOUCOM_API_URL,
                    headers=headers,
                    params=params,
                    timeout=self.timeout,
                )
                response.raise_for_status()
                return response.json()
            except requests.RequestException as e:
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY)
                else:
                    raise


# ============================================================================
# Normalization
# ============================================================================

def normalize_youcom_response(raw: Dict[str, Any]) -> List[ResearchSource]:
    """Normalize You.com API response to ResearchSource list.

    Handles various response formats gracefully.
    """
    sources = []

    # You.com response structure: { "hits": [...] } or similar
    hits = raw.get("hits", [])
    if not hits:
        # Fallback: check for "results" or "web_results"
        hits = raw.get("results", raw.get("web_results", []))

    for idx, hit in enumerate(hits[:20]):  # Cap at 20 sources
        title = hit.get("title", hit.get("name", "Untitled"))
        url = hit.get("url", hit.get("link", ""))
        snippet = hit.get("snippets", hit.get("description", hit.get("snippet")))

        if isinstance(snippet, list):
            snippet = " ".join(snippet[:2])  # Join first 2 snippets
        elif snippet:
            snippet = str(snippet)[:500]  # Truncate long snippets

        # Extract published date if available
        published = hit.get("published_date", hit.get("date"))

        if url:  # Only include if we have a URL
            sources.append(
                ResearchSource(
                    title=title,
                    url=url,
                    snippet=snippet,
                    provider_rank=idx + 1,
                    published_date=published,
                )
            )

    return sources


# ============================================================================
# Caching
# ============================================================================

def _cache_key(query: str, n_results: int) -> str:
    """Compute cache key for query."""
    normalized_query = query.strip().lower()
    payload = json.dumps({"query": normalized_query, "n_results": n_results}, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


def _cache_path(cache_key: str) -> Path:
    """Get cache file path for a cache key."""
    return _get_cache_dir() / f"{cache_key}.json"


def read_cache(query: str, n_results: int) -> Optional[List[ResearchSource]]:
    """Read cached results if available."""
    key = _cache_key(query, n_results)
    path = _cache_path(key)

    if not path.exists():
        return None

    try:
        with open(path, "r") as f:
            data = json.load(f)
        return [ResearchSource(**s) for s in data["sources"]]
    except Exception:
        return None


def write_cache(query: str, n_results: int, sources: List[ResearchSource]):
    """Write results to cache."""
    key = _cache_key(query, n_results)
    path = _cache_path(key)

    data = {
        "cache_key": key,
        "query": query,
        "n_results": n_results,
        "cached_at": time.time(),
        "sources": [s.model_dump() for s in sources],
    }

    # Atomic write
    temp_path = path.with_suffix(".tmp")
    with open(temp_path, "w") as f:
        json.dump(data, f, indent=2)
    temp_path.rename(path)


# ============================================================================
# High-level API
# ============================================================================

def search_with_cache(
    query: str,
    n_results: int = 5,
    client: Optional[YouComClient] = None,
) -> List[ResearchSource]:
    """Search You.com with persistent caching.

    Args:
        query: Search query
        n_results: Number of results to fetch
        client: Optional YouComClient (for DI/testing)

    Returns:
        List of ResearchSource (from cache or fresh API call)

    Raises:
        requests.RequestException: if API fails and no cache available
    """
    # Check cache first
    cached = read_cache(query, n_results)
    if cached is not None:
        return cached

    # Cache miss - fetch from API
    if client is None:
        client = YouComClient()

    raw = client.search(query, n_results)
    sources = normalize_youcom_response(raw)

    # Write to cache
    write_cache(query, n_results, sources)

    return sources


# ============================================================================
# Extraction heuristics (deterministic, no LLM)
# ============================================================================

def extract_insights(sources: List[ResearchSource], query: str) -> ResearchExtraction:
    """Extract structured insights from sources using heuristics.

    This is deterministic - no LLM calls. Uses keyword matching and templates.
    """
    # Aggregate all text
    all_text = " ".join(
        [s.title + " " + (s.snippet or "") for s in sources]
    ).lower()

    assumptions = []
    knobs = []
    failure_modes = []
    tests = []

    # Assumptions keywords
    if any(
        kw in all_text
        for kw in ["normal distribution", "gaussian", "mean reversion", "stationary"]
    ):
        assumptions.append("Assumes price returns follow known statistical properties")

    if "momentum" in all_text or "trend following" in all_text:
        assumptions.append("Assumes trends persist over signal window")

    if "volume" in all_text and "liquidity" in all_text:
        assumptions.append("Assumes sufficient liquidity for execution")

    # Knobs (tunable parameters)
    if any(kw in all_text for kw in ["period", "window", "lookback"]):
        knobs.append("Lookback period / window size")

    if any(kw in all_text for kw in ["threshold", "trigger", "signal level"]):
        knobs.append("Signal threshold levels")

    if "stop loss" in all_text or "take profit" in all_text:
        knobs.append("Risk management parameters (SL/TP)")

    if "position siz" in all_text or "allocation" in all_text:
        knobs.append("Position sizing / allocation weights")

    # Failure modes
    if "overfitting" in all_text or "curve fitting" in all_text:
        failure_modes.append("Overfitting to historical patterns")

    if "regime change" in all_text or "non-stationary" in all_text:
        failure_modes.append("Regime change / non-stationarity")

    if "slippage" in all_text or "execution" in all_text:
        failure_modes.append("Slippage and execution costs")

    if "drawdown" in all_text or "volatility" in all_text:
        failure_modes.append("Excessive drawdown during volatile periods")

    # Suggested tests
    if "walk forward" in all_text or "out of sample" in all_text:
        tests.append("Walk-forward out-of-sample validation")

    if "monte carlo" in all_text or "bootstrap" in all_text:
        tests.append("Monte Carlo / bootstrap robustness testing")

    if "regime" in all_text:
        tests.append("Cross-regime performance evaluation")

    tests.append("Parameter sensitivity analysis")
    tests.append("Drawdown stress testing")

    return ResearchExtraction(
        assumptions=assumptions or ["No specific assumptions identified"],
        knobs=knobs or ["Standard strategy parameters"],
        known_failure_modes=failure_modes or ["General market risk"],
        suggested_tests=tests,
    )


# ============================================================================
# ResearchPack factory
# ============================================================================

def create_research_pack(
    query: str,
    n_results: int = 5,
    client: Optional[YouComClient] = None,
) -> ResearchPack:
    """Create a ResearchPack from a query.

    Args:
        query: Search query (or URL - will be incorporated into query)
        n_results: Number of results
        client: Optional YouComClient for DI

    Returns:
        ResearchPack with sources and extractions
    """
    # If query looks like a URL, incorporate it
    if query.startswith("http://") or query.startswith("https://"):
        query = f"algorithmic trading strategies {query}"

    # Fetch sources (cached or fresh)
    sources = search_with_cache(query, n_results, client)

    # Extract insights
    extracted = extract_insights(sources, query)

    # Compute fingerprint
    fingerprint = ResearchPack.compute_fingerprint(query, sources)

    # Truncate raw if it would be huge (keep first 10KB)
    raw_data = {"query": query, "n_results": n_results, "source_count": len(sources)}

    return ResearchPack(
        id=fingerprint[:16],  # Use first 16 chars of fingerprint as ID
        created_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
        query=query,
        provider="youcom",
        sources=sources,
        extracted=extracted,
        raw=raw_data,
        fingerprint=fingerprint,
    )
