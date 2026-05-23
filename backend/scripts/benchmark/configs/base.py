"""Shared contract for benchmark agent runners.

Every config implements ``AgentRunner`` and is keyed in ``registry.CONFIG_REGISTRY``
by a stable string name. The runner driver calls ``runner.run(inp)``, validates
the returned analysis against the production ``ProductSafetyAnalysis`` schema,
then feeds it through ``HarmScoreCalculator.calculate`` before recording.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AgentRunInput:
    """Frozen inputs handed to each config for a single run."""

    product_data: Dict[str, Any]
    product_url: str
    allergen_db: List[Dict[str, Any]]
    pfas_db: List[Dict[str, Any]]
    search_service: Any  # SearchToolService — typed Any to keep this module light
    tracer: Any          # benchmark.tracer.Tracer
    token_tracker: Any   # backend.src.infrastructure.token_tracker.TokenTracker
    supabase_client: Any = None
    allergen_profile: Optional[List[str]] = None
    timeout_seconds: float = 180.0


@dataclass
class AgentRunOutput:
    """What every config returns."""

    analysis: Dict[str, Any]
    failure_type: Optional[str] = None
    retry_count: int = 0
    notes: Dict[str, Any] = field(default_factory=dict)


class AgentRunner(Protocol):
    name: str
    supports_caching: bool

    async def run(self, inp: AgentRunInput) -> AgentRunOutput: ...


class BaseAgentRunner:
    """Convenience base — gives subclasses a uniform tracer wrapper."""

    name: str = "_base"
    supports_caching: bool = False

    def __init__(self) -> None:
        if not self.name or self.name.startswith("_"):
            raise ValueError(
                f"{type(self).__name__} must set a non-underscore `name` class attr"
            )

    @contextmanager
    def _record_phase(self, tracer: Any, phase: str):
        """Wrap a logical phase so its latency lands in tracer.per_phase_latency_ms."""
        if tracer is None:
            yield
            return
        with tracer.phase(phase):
            yield

    async def run(self, inp: AgentRunInput) -> AgentRunOutput:  # pragma: no cover
        raise NotImplementedError


__all__ = ["AgentRunInput", "AgentRunOutput", "AgentRunner", "BaseAgentRunner"]
