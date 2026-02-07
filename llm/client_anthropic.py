"""Anthropic client for JSON completion."""

import json
import time
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

import anthropic
import config
from llm.cache import get_cached_response, save_cached_response, record_api_call
from llm.transcripts import record_transcript


# Create llm_logs directory
LLM_LOGS_DIR = config.RESULTS_DIR / "llm_logs"
LLM_LOGS_DIR.mkdir(exist_ok=True, parents=True)


def complete_json(
    system_prompt: str,
    user_prompt: str,
    model: str = "claude-sonnet-4-20250514",
    temperature: float = 0.7,
    max_tokens: int = 4000,
    max_retries: int = 3,
    use_cache: bool = True,
    transcript_meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Complete JSON using Anthropic API with caching.

    Args:
        system_prompt: System prompt
        user_prompt: User prompt (should request JSON output)
        model: Model name (default: claude-sonnet-4-20250514)
        temperature: Sampling temperature (0-1)
        max_tokens: Maximum tokens to generate
        max_retries: Max retry attempts for transient errors
        use_cache: Enable response caching (default True)

    Returns:
        Parsed JSON dict

    Raises:
        anthropic.APIError: API errors
        json.JSONDecodeError: Invalid JSON response
    """
    if not config.ANTHROPIC_API_KEY:
        raise ValueError("ANTHROPIC_API_KEY not set in environment")

    # Check cache first
    def _record(meta, parsed=None, error=None, cached_flag=False, raw_text=None):
        if not meta:
            return
        extra = dict(meta.get("extra") or {})
        artifact = meta.get("artifact")
        record_transcript(
            run_id=meta.get("run_id"),
            stage=meta.get("stage"),
            provider="anthropic",
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            raw_response_text=raw_text or '',
            parsed_json=parsed,
            error=error,
            suffix=meta.get("suffix"),
            artifact=artifact,
            cached=cached_flag,
            extra=extra,
        )

    if use_cache:
        cached = get_cached_response(system_prompt, user_prompt, model, temperature)
        if cached is not None:
            _record(transcript_meta, parsed=cached, cached_flag=True, raw_text=json.dumps(cached))
            return cached

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    # Retry loop for transient errors
    last_error = None
    for attempt in range(max_retries):
        try:
            response = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": user_prompt}
                ]
            )

            raw_response = response.content[0].text

            # Log raw response
            _log_response("anthropic", system_prompt, user_prompt, raw_response, model)

            # Strip markdown code blocks if present (Claude often wraps JSON)
            cleaned = raw_response.strip()
            if cleaned.startswith("```"):
                # Remove opening ```json or ``` line
                first_newline = cleaned.index('\n') if '\n' in cleaned else len(cleaned)
                cleaned = cleaned[first_newline + 1:]
                # Remove closing ```
                if cleaned.rstrip().endswith("```"):
                    cleaned = cleaned.rstrip()[:-3].rstrip()

            parsed = None
            parse_error = None
            try:
                parsed = json.loads(cleaned)
            except json.JSONDecodeError as exc:
                parse_error = str(exc)
                _record(transcript_meta, parsed=None, error=parse_error, raw_text=raw_response)
                raise

            # Record API call and save to cache
            tokens_used = response.usage.input_tokens + response.usage.output_tokens if hasattr(response, 'usage') else 0
            cost_estimate = tokens_used * 0.000015  # Rough estimate for Claude Sonnet
            record_api_call("anthropic", tokens=tokens_used, cost=cost_estimate)

            _record(transcript_meta, parsed=parsed, raw_text=raw_response)

            if use_cache:
                save_cached_response(system_prompt, user_prompt, model, temperature, parsed, tokens_used)

            return parsed

        except (anthropic.APITimeoutError, anthropic.APIConnectionError) as e:
            # Transient errors - retry
            last_error = e
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
                continue
            else:
                raise

        except anthropic.APIError as e:
            # Non-transient API errors - fail immediately
            raise

    # Should not reach here
    raise last_error


def _log_response(
    provider: str,
    system_prompt: str,
    user_prompt: str,
    response: str,
    model: str
):
    """Log LLM request/response to file."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    log_file = LLM_LOGS_DIR / f"{provider}_{timestamp}.json"

    log_data = {
        "timestamp": datetime.now().isoformat(),
        "provider": provider,
        "model": model,
        "system_prompt": system_prompt,
        "user_prompt": user_prompt,
        "response": response,
    }

    with open(log_file, 'w') as f:
        json.dump(log_data, f, indent=2)
