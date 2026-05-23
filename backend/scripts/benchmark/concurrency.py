"""Concurrency sub-benchmark.

Runs N ∈ {1, 5, 15} concurrent requests × 5 requests per N × 3 representative
configs. Captures throughput (requests/sec), p50/p95/p99 latency, error rate.

Total: ~75 analyses × ~$0.20 ≈ $15.
"""

from __future__ import annotations

import asyncio
import json
import logging
import statistics
import time
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

DEFAULT_CONFIGS = [
    "claude_agentsdk_async_cached",
    "cohere_asyncv2_cached",
    "claude_cohere_coordinated_cached",
]


async def _one_request(runner: Any, inp_factory) -> Dict[str, Any]:
    inp = inp_factory()
    t0 = time.perf_counter()
    error = None
    try:
        out = await runner.run(inp)
        failure = out.failure_type
    except Exception as e:
        failure = "exception"
        error = str(e)
    latency_ms = (time.perf_counter() - t0) * 1000
    return {"latency_ms": latency_ms, "failure": failure, "error": error}


async def run_concurrency_benchmark(
    *,
    dataset_path: Path,
    output_dir: Path,
    configs: List[str] = None,
    levels: List[int] = (1, 5, 15),
    requests_per_level: int = 5,
) -> Dict[str, Any]:
    from src.infrastructure.token_tracker import TokenTracker
    from src.infrastructure.search_tool_service import SearchToolService
    from src.infrastructure.database import db as _db
    from .configs.base import AgentRunInput
    from .configs.registry import get_runner
    from .tracer import Tracer

    configs = configs or DEFAULT_CONFIGS
    output_dir.mkdir(parents=True, exist_ok=True)
    dataset = json.loads(dataset_path.read_text())
    product_row = dataset[0]  # use a single product to factor out variability

    supabase_client = _db.client if _db.is_available else None
    allergen_db = await _db.get_all_allergens() if _db.is_available else []
    pfas_db = await _db.get_all_pfas() if _db.is_available else []

    search_service = SearchToolService(supabase_client=supabase_client)

    def make_input():
        tracer = Tracer(config="concurrency", product_id=product_row["product_id"], run_idx=0)
        tt = TokenTracker()
        tt.start_analysis("concurrency")
        return AgentRunInput(
            product_data=product_row["product_data"],
            product_url=product_row.get("product_url", ""),
            allergen_db=allergen_db,
            pfas_db=pfas_db,
            search_service=search_service,
            tracer=tracer,
            token_tracker=tt,
            supabase_client=supabase_client,
        )

    results: Dict[str, Any] = {}
    for cfg in configs:
        runner = get_runner(cfg)
        for n in levels:
            wall = time.perf_counter()
            batch = await asyncio.gather(*[
                _one_request(runner, make_input) for _ in range(requests_per_level * n)
            ], return_exceptions=False)
            wall_ms = (time.perf_counter() - wall) * 1000
            lats = [b["latency_ms"] for b in batch]
            failures = sum(1 for b in batch if b["failure"])
            results.setdefault(cfg, {})[f"n={n}"] = {
                "requests": len(batch),
                "wall_ms": wall_ms,
                "throughput_rps": (len(batch) / (wall_ms / 1000.0)) if wall_ms else 0.0,
                "p50_ms": statistics.median(lats) if lats else 0.0,
                "p95_ms": _quantile(lats, 0.95),
                "p99_ms": _quantile(lats, 0.99),
                "error_rate": failures / len(batch) if batch else 0.0,
            }

    (output_dir / "concurrency.json").write_text(json.dumps(results, indent=2))
    return results


def _quantile(values: List[float], q: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    idx = int(q * (len(s) - 1))
    return s[idx]
