"""LLM response caching and budget tracking."""

import json
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, field

import config


# Create cache directory
LLM_CACHE_DIR = config.RESULTS_DIR / "llm_cache"
LLM_CACHE_DIR.mkdir(exist_ok=True, parents=True)


@dataclass
class LLMBudget:
    """Tracks LLM usage for a run."""
    total_calls: int = 0
    total_tokens: int = 0  # If available from API
    cache_hits: int = 0
    cache_misses: int = 0

    # Provider-specific counts
    openai_calls: int = 0
    anthropic_calls: int = 0

    # Cost estimates (rough, based on known pricing)
    estimated_cost_usd: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for JSON serialization."""
        return {
            'total_calls': self.total_calls,
            'total_tokens': self.total_tokens,
            'cache_hits': self.cache_hits,
            'cache_misses': self.cache_misses,
            'openai_calls': self.openai_calls,
            'anthropic_calls': self.anthropic_calls,
            'estimated_cost_usd': round(self.estimated_cost_usd, 2),
        }


# Global budget tracker (reset per run)
_current_budget = LLMBudget()


_global_budget = LLMBudget()


def reset_budget():
    """Reset budget tracker."""
    global _current_budget
    _current_budget = LLMBudget()


def get_budget() -> LLMBudget:
    """Get current budget."""
    return _current_budget


def get_global_budget() -> LLMBudget:
    """Get budget aggregated since server start."""
    return _global_budget


def _compute_cache_key(system_prompt: str, user_prompt: str, model: str, temperature: float) -> str:
    """Compute cache key from prompts.

    Note: Temperature included but rounded to 1 decimal for better hit rate.
    """
    temp_rounded = round(temperature, 1)
    cache_input = f"{model}|{temp_rounded}|{system_prompt}|{user_prompt}"
    return hashlib.sha256(cache_input.encode()).hexdigest()


def get_cached_response(
    system_prompt: str,
    user_prompt: str,
    model: str,
    temperature: float
) -> Optional[Dict[str, Any]]:
    """Get cached LLM response if exists.

    Args:
        system_prompt: System prompt
        user_prompt: User prompt
        model: Model name
        temperature: Temperature (rounded to 1 decimal)

    Returns:
        Cached response dict or None if not found
    """
    cache_key = _compute_cache_key(system_prompt, user_prompt, model, temperature)
    cache_file = LLM_CACHE_DIR / f"{cache_key}.json"

    if cache_file.exists():
        try:
            with open(cache_file, 'r') as f:
                cached = json.load(f)
            _current_budget.cache_hits += 1
            _global_budget.cache_hits += 1
            return cached.get('response')
        except Exception:
            return None

    _current_budget.cache_misses += 1
    _global_budget.cache_misses += 1
    return None


def save_cached_response(
    system_prompt: str,
    user_prompt: str,
    model: str,
    temperature: float,
    response: Dict[str, Any],
    tokens_used: int = 0,
):
    """Save LLM response to cache.

    Args:
        system_prompt: System prompt
        user_prompt: User prompt
        model: Model name
        temperature: Temperature
        response: Parsed response dict
        tokens_used: Token count if available
    """
    cache_key = _compute_cache_key(system_prompt, user_prompt, model, temperature)
    cache_file = LLM_CACHE_DIR / f"{cache_key}.json"

    cache_data = {
        'cache_key': cache_key,
        'model': model,
        'temperature': temperature,
        'system_prompt_hash': hashlib.md5(system_prompt.encode()).hexdigest(),
        'user_prompt_hash': hashlib.md5(user_prompt.encode()).hexdigest(),
        'response': response,
        'tokens_used': tokens_used,
    }

    with open(cache_file, 'w') as f:
        json.dump(cache_data, f, indent=2)


def record_api_call(provider: str, tokens: int = 0, cost: float = 0.0):
    """Record an API call in budget.

    Args:
        provider: "openai" or "anthropic"
        tokens: Token count if available
        cost: Cost estimate if available
    """
    _current_budget.total_calls += 1
    _current_budget.total_tokens += tokens
    _current_budget.estimated_cost_usd += cost

    if provider == "openai":
        _current_budget.openai_calls += 1
        _global_budget.openai_calls += 1
    elif provider == "anthropic":
        _current_budget.anthropic_calls += 1
        _global_budget.anthropic_calls += 1

    _global_budget.total_calls += 1
    _global_budget.total_tokens += tokens
    _global_budget.estimated_cost_usd += cost
