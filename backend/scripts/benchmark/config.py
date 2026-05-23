"""Benchmark configuration - controlled parameters for fair comparison."""

from dataclasses import dataclass
from typing import List


@dataclass
class BenchmarkConfig:
    """Configuration for benchmark runs."""

    # Temperature - MUST be identical for fair comparison
    temperature: float = 0.3

    # Number of runs per product per agent
    runs_per_product: int = 5

    # Agents to test
    agents: List[str] = None

    # Maximum iterations per agent analysis
    max_iterations: int = 15

    # Search settings
    max_searches_per_analysis: int = 15

    def __post_init__(self):
        if self.agents is None:
            self.agents = ["claude", "cohere_langgraph", "cohere_native"]


# Default configuration
BENCHMARK_CONFIG = BenchmarkConfig()


# Cost estimates (for budget tracking)
COST_ESTIMATES = {
    "claude": {
        "input_per_1m": 3.00,
        "output_per_1m": 15.00,
        "avg_tokens_per_run": 40000,
    },
    "cohere_langgraph": {
        "input_per_1m": 2.50,
        "output_per_1m": 10.00,
        "avg_tokens_per_run": 35000,
    },
    "cohere_native": {
        "input_per_1m": 2.50,
        "output_per_1m": 10.00,
        "avg_tokens_per_run": 35000,
    },
    "search": {
        "per_search": 0.008,
        "avg_searches_per_run": 10,
    },
}


def estimate_total_cost(num_products: int, config: BenchmarkConfig = None) -> float:
    """Estimate total cost for benchmark run.

    Args:
        num_products: Number of products to test
        config: Benchmark configuration (uses default if not provided)

    Returns:
        Estimated total cost in USD
    """
    config = config or BENCHMARK_CONFIG

    total_runs = num_products * len(config.agents) * config.runs_per_product

    # Token costs
    token_cost = 0.0
    for agent in config.agents:
        agent_runs = num_products * config.runs_per_product
        est = COST_ESTIMATES.get(agent, COST_ESTIMATES["claude"])
        avg_cost_per_run = (
            est["avg_tokens_per_run"] * est["input_per_1m"] / 1_000_000 +
            est["avg_tokens_per_run"] * 0.1 * est["output_per_1m"] / 1_000_000
        )
        token_cost += agent_runs * avg_cost_per_run

    # Search costs
    search_est = COST_ESTIMATES["search"]
    search_cost = total_runs * search_est["avg_searches_per_run"] * search_est["per_search"]

    return token_cost + search_cost
