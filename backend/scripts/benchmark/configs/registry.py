"""Config registry — maps stable names to AgentRunner factory callables.

Imports are lazy so a missing optional dep (e.g. claude-agent-sdk not yet
installed) doesn't blow up importing the registry — the user discovers it
only when they try to instantiate that specific config.
"""

from __future__ import annotations

from typing import Callable, Dict, List

from .base import AgentRunner


# Each entry is name -> lazy import string "module:factory_callable"
_CONFIG_LAZY: Dict[str, str] = {
    "claude_agentsdk_async_cached": "scripts.benchmark.configs.claude_agentsdk_async_cached:make_runner",
    "cohere_asyncv2_cached":         "scripts.benchmark.configs.cohere_asyncv2_cached:make_runner",
    "claude_langgraph12_cached":     "scripts.benchmark.configs.claude_langgraph12_cached:make_runner",
    "cohere_langgraph12":            "scripts.benchmark.configs.cohere_langgraph12:make_runner",
    "claude_cohere_coordinated_cached": "scripts.benchmark.configs.claude_cohere_coordinated_cached:make_runner",
}


def list_configs() -> List[str]:
    return sorted(_CONFIG_LAZY)


def get_runner(name: str, **kwargs) -> AgentRunner:
    if name not in _CONFIG_LAZY:
        raise KeyError(
            f"Unknown config '{name}'. Known: {', '.join(list_configs())}"
        )
    module_path, factory_name = _CONFIG_LAZY[name].split(":")
    import importlib

    module = importlib.import_module(module_path)
    factory: Callable[..., AgentRunner] = getattr(module, factory_name)
    return factory(**kwargs)


__all__ = ["list_configs", "get_runner"]
