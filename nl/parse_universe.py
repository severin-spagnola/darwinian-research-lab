"""Natural language universe specification parser.

TODO: Implement LLM-based parsing of universe descriptions.
Example: "trade the top 10 tech stocks" -> UniverseSpec
"""

from graph.schema import UniverseSpec


def parse_universe(nl_description: str) -> UniverseSpec:
    """Parse natural language universe description into UniverseSpec.

    Args:
        nl_description: Natural language description of universe

    Returns:
        UniverseSpec object
    """
    raise NotImplementedError("Universe parsing not yet implemented")
