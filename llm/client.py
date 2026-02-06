"""LLM client for OpenAI and Anthropic APIs.

TODO: Implement unified LLM client for:
- Strategy compilation (NL -> StrategyGraph)
- Mutation generation
- Strategy explanation
"""

import config


class LLMClient:
    """Unified client for OpenAI and Anthropic APIs."""

    def __init__(self):
        self.openai_key = config.OPENAI_API_KEY
        self.anthropic_key = config.ANTHROPIC_API_KEY

    def compile_strategy(self, nl_description: str):
        """Compile natural language description to StrategyGraph."""
        raise NotImplementedError("LLM compilation not yet implemented")

    def generate_mutation(self, strategy_graph):
        """Generate mutation suggestions for a strategy."""
        raise NotImplementedError("LLM mutation not yet implemented")
