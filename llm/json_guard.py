"""JSON validation and repair for LLM outputs."""

import json
from typing import Dict, Any, TypeVar, Type
from pydantic import BaseModel, ValidationError

from llm import client_openai, client_anthropic


T = TypeVar('T', bound=BaseModel)


def validate_and_repair(
    llm_output: Dict[str, Any],
    model_class: Type[T],
    provider: str = "openai",
    max_repair_attempts: int = 1,
) -> T:
    """Validate LLM JSON output against Pydantic model with optional repair.

    Args:
        llm_output: Raw JSON dict from LLM
        model_class: Pydantic model class to validate against
        provider: "openai" or "anthropic" for repair attempts
        max_repair_attempts: Max repair attempts (default 1)

    Returns:
        Validated Pydantic model instance

    Raises:
        ValidationError: If validation fails after all repair attempts
    """
    # Try direct validation first
    try:
        return model_class(**llm_output)
    except ValidationError as e:
        # Validation failed - attempt repair if allowed
        if max_repair_attempts == 0:
            raise

        # Try one repair
        repaired = _attempt_repair(llm_output, model_class, e, provider)

        # Validate repaired JSON
        try:
            return model_class(**repaired)
        except ValidationError as e2:
            # Still invalid - raise final error
            raise ValidationError(
                f"JSON repair failed. Original error: {e}\nRepair error: {e2}"
            )


def _attempt_repair(
    invalid_json: Dict[str, Any],
    model_class: Type[BaseModel],
    error: ValidationError,
    provider: str,
) -> Dict[str, Any]:
    """Attempt to repair invalid JSON with LLM.

    Args:
        invalid_json: Invalid JSON dict
        model_class: Target Pydantic model
        error: ValidationError from initial validation
        provider: "openai" or "anthropic"

    Returns:
        Repaired JSON dict (not validated)
    """
    # Get schema from Pydantic model
    schema = model_class.model_json_schema()

    system_prompt = """You are a JSON repair tool. Fix the invalid JSON to match the schema.
Output ONLY valid JSON, no explanations."""

    user_prompt = f"""Fix this JSON to match the schema.

SCHEMA:
{json.dumps(schema, indent=2)}

VALIDATION ERROR:
{str(error)}

INVALID JSON:
{json.dumps(invalid_json, indent=2)}

Output the corrected JSON only."""

    # Call LLM for repair
    if provider == "openai":
        repaired = client_openai.complete_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.0,  # Deterministic repair
            max_tokens=4000,
        )
    elif provider == "anthropic":
        repaired = client_anthropic.complete_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.0,
            max_tokens=4000,
        )
    else:
        raise ValueError(f"Unknown provider: {provider}")

    return repaired


def validate_strategy_graph(llm_output: Dict[str, Any], provider: str = "openai"):
    """Validate and repair StrategyGraph JSON.

    Args:
        llm_output: JSON dict from LLM
        provider: "openai" or "anthropic"

    Returns:
        Validated StrategyGraph instance

    Raises:
        ValidationError: If validation fails
    """
    from graph.schema import StrategyGraph

    return validate_and_repair(llm_output, StrategyGraph, provider)


def validate_patch_set(llm_output: Dict[str, Any], provider: str = "openai"):
    """Validate and repair PatchSet JSON.

    Args:
        llm_output: JSON dict from LLM
        provider: "openai" or "anthropic"

    Returns:
        Validated PatchSet instance (to be defined)

    Raises:
        ValidationError: If validation fails
    """
    # Import PatchSet model (to be created in evolution module)
    # For now, just return dict
    # TODO: Implement PatchSet Pydantic model in evolution/patches.py
    return llm_output
