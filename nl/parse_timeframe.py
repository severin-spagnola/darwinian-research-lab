"""Natural language timeframe specification parser.

TODO: Implement LLM-based parsing of timeframe descriptions.
Example: "test on 5 minute bars from Jan to Dec 2024" -> TimeframeSpec
"""

from graph.schema import TimeframeSpec


def parse_timeframe(nl_description: str) -> TimeframeSpec:
    """Parse natural language timeframe description into TimeframeSpec.

    Args:
        nl_description: Natural language description of timeframe

    Returns:
        TimeframeSpec object
    """
    raise NotImplementedError("Timeframe parsing not yet implemented")
