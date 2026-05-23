"""Per-run tracing — captures each tool call + per-phase latencies.

The runner creates one ``Tracer`` per (config, product, run) and passes it
through ``AgentRunInput``. Each config wraps logical phases with
``tracer.phase(name)`` (extract / db_match / classify / research / score /
save). The traced ``SearchToolService`` wrapper records each search call.

The serialized trace lands in ``output/runs/{config}/{product}/run{N}/trace.json``
so a single run can be replayed for inspection without re-running the model.
"""

from __future__ import annotations

import json
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ToolCall:
    tool: str                # "web_search" / "lookup_ingredient_research" / ...
    args: Dict[str, Any]
    latency_ms: float
    cached: bool = False
    error: Optional[str] = None
    result_preview: str = ""  # first 200 chars

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool": self.tool,
            "args": self.args,
            "latency_ms": round(self.latency_ms, 2),
            "cached": self.cached,
            "error": self.error,
            "result_preview": self.result_preview,
        }


@dataclass
class PhaseTiming:
    name: str
    started_at: float
    ended_at: Optional[float] = None

    @property
    def latency_ms(self) -> float:
        if self.ended_at is None:
            return 0.0
        return (self.ended_at - self.started_at) * 1000


@dataclass
class RunTrace:
    config: str
    product_id: str
    run_idx: int
    tool_calls: List[ToolCall] = field(default_factory=list)
    phases: List[PhaseTiming] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "config": self.config,
            "product_id": self.product_id,
            "run_idx": self.run_idx,
            "tool_calls": [c.to_dict() for c in self.tool_calls],
            "phases": [
                {"name": p.name, "latency_ms": round(p.latency_ms, 2)}
                for p in self.phases
            ],
            "per_phase_latency_ms": self.per_phase_latency_ms(),
            "tool_call_count": len(self.tool_calls),
        }

    def per_phase_latency_ms(self) -> Dict[str, float]:
        out: Dict[str, float] = {}
        for p in self.phases:
            out[p.name] = out.get(p.name, 0.0) + p.latency_ms
        return out


class Tracer:
    """Single-run tracer."""

    def __init__(self, config: str, product_id: str, run_idx: int) -> None:
        self.trace = RunTrace(config=config, product_id=product_id, run_idx=run_idx)

    @contextmanager
    def phase(self, name: str):
        ph = PhaseTiming(name=name, started_at=time.perf_counter())
        self.trace.phases.append(ph)
        try:
            yield
        finally:
            ph.ended_at = time.perf_counter()

    def record_tool_call(
        self,
        tool: str,
        args: Dict[str, Any],
        latency_ms: float,
        cached: bool = False,
        error: Optional[str] = None,
        result_preview: str = "",
    ) -> None:
        self.trace.tool_calls.append(
            ToolCall(
                tool=tool,
                args=dict(args),
                latency_ms=latency_ms,
                cached=cached,
                error=error,
                result_preview=(result_preview or "")[:200],
            )
        )

    def to_json(self) -> str:
        return json.dumps(self.trace.to_dict(), default=str, indent=2)
