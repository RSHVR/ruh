"""Main eval driver.

For each (config, product, run) tuple:
  1. Build AgentRunInput (frozen fixture + shared SearchToolService + Tracer
     + per-run TokenTracker).
  2. Call ``runner.run(input)`` — wall-clock timed.
  3. Validate output against ProductSafetyAnalysis; set failure_type if invalid.
  4. Score via HarmScoreCalculator.calculate (deterministic).
  5. Compute correctness/divergence metrics.
  6. Persist RunMetrics + RunTrace + analysis to output/runs/...
  7. Update budget + checkpoint.

The driver is concurrency-controlled per-provider (Anthropic / Cohere) via
semaphores so we don't blow rate limits when N>1.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from .budget import BudgetExceeded, BudgetTracker
from .checkpoint import Checkpoint, compute_config_hash, install_signal_flush
from .configs.base import AgentRunInput
from .configs.registry import get_runner, list_configs
from .metrics import RunMetrics, confusion, jaccard
from .observability import root_run
from .tracer import Tracer

logger = logging.getLogger(__name__)


PROVIDER_SEMAPHORES: Dict[str, asyncio.Semaphore] = {}


def _provider_for(config_name: str) -> str:
    if config_name.startswith("cohere_"):
        return "cohere"
    if config_name.startswith("claude_cohere_"):
        return "both"
    return "anthropic"


def _get_semaphore(provider: str, anthropic_limit: int, cohere_limit: int) -> asyncio.Semaphore:
    if provider not in PROVIDER_SEMAPHORES:
        limit = cohere_limit if provider == "cohere" else anthropic_limit
        PROVIDER_SEMAPHORES[provider] = asyncio.Semaphore(limit)
    return PROVIDER_SEMAPHORES[provider]


def _load_dataset(dataset_path: Path) -> List[Dict[str, Any]]:
    return json.loads(dataset_path.read_text())


def _load_ground_truth(path: Path) -> Dict[str, Dict[str, Any]]:
    if not path.exists():
        return {}
    return {row["product_id"]: row for row in json.loads(path.read_text())}


def _compute_correctness(
    analysis: Dict[str, Any],
    ground_truth: Dict[str, Any],
    harm_score: int,
) -> Dict[str, Any]:
    detected_allergens = [a.get("name", "") for a in analysis.get("allergens_detected", [])]
    detected_pfas = [p.get("name", "") for p in analysis.get("pfas_detected", [])]
    a_tp, a_fp, a_fn = confusion(detected_allergens, ground_truth.get("expected_allergens", []))
    p_tp, p_fp, p_fn = confusion(detected_pfas, ground_truth.get("expected_pfas", []))
    hr = ground_truth.get("expected_harm_score_range")
    in_range = None
    if hr and len(hr) == 2:
        in_range = bool(hr[0] <= harm_score <= hr[1])
    return {
        "allergen_tp": a_tp, "allergen_fp": a_fp, "allergen_fn": a_fn,
        "pfas_tp": p_tp, "pfas_fp": p_fp, "pfas_fn": p_fn,
        "harm_score_in_expected_range": in_range,
    }


def _compute_divergence(
    analysis: Dict[str, Any],
    reference: Optional[Dict[str, Any]],
    harm_score: int,
) -> Dict[str, Any]:
    if not reference:
        return {}
    ref_analysis = reference.get("analysis", {})
    return {
        "reference_jaccard_allergens": jaccard(
            [a.get("name", "") for a in analysis.get("allergens_detected", [])],
            [a.get("name", "") for a in ref_analysis.get("allergens_detected", [])],
        ),
        "reference_jaccard_pfas": jaccard(
            [p.get("name", "") for p in analysis.get("pfas_detected", [])],
            [p.get("name", "") for p in ref_analysis.get("pfas_detected", [])],
        ),
        "reference_harm_delta": int(harm_score - reference.get("harm_score", harm_score)),
    }


async def _run_one(
    *,
    config_name: str,
    runner_obj: Any,
    product_row: Dict[str, Any],
    run_idx: int,
    allergen_db: List[Dict[str, Any]],
    pfas_db: List[Dict[str, Any]],
    search_service: Any,
    supabase_client: Any,
    output_dir: Path,
    budget: BudgetTracker,
    ground_truth: Dict[str, Dict[str, Any]],
    reference_index: Dict[str, Dict[str, Any]],
) -> RunMetrics:
    from src.infrastructure.token_tracker import TokenTracker
    from src.domain.harm_calculator import HarmScoreCalculator
    from src.domain.extraction_schemas import ProductSafetyAnalysis
    from pydantic import ValidationError

    product_id = product_row["product_id"]
    tracer = Tracer(config=config_name, product_id=product_id, run_idx=run_idx)
    token_tracker = TokenTracker()
    token_tracker.start_analysis(f"{config_name}/{product_id}/run{run_idx}")

    inp = AgentRunInput(
        product_data=product_row["product_data"],
        product_url=product_row.get("product_url", ""),
        allergen_db=allergen_db,
        pfas_db=pfas_db,
        search_service=search_service,
        tracer=tracer,
        token_tracker=token_tracker,
        supabase_client=supabase_client,
        allergen_profile=None,
    )

    started = time.perf_counter()
    failure_type: Optional[str] = None
    result = None
    analysis: Dict[str, Any] = {}
    retry_count = 0
    # One LangSmith root trace per run; every nested LLM/tool call attaches here
    # (no-op when LANGSMITH_TRACING is unset).
    with root_run(
        f"{config_name}::{product_id}::run{run_idx}",
        metadata={"config": config_name, "product_id": product_id,
                  "run_idx": run_idx, "mode": output_dir.name},
        tags=[config_name, _provider_for(config_name)],
    ) as _ls_rt:
        try:
            result = await runner_obj.run(inp)
            analysis = result.analysis or {}
            failure_type = result.failure_type
            retry_count = result.retry_count
        except Exception as e:
            logger.error("Runner %s threw: %s", config_name, e, exc_info=True)
            analysis = {}
            failure_type = "runner_exception"
            retry_count = 0

        total_latency_ms = (time.perf_counter() - started) * 1000

        # Validate against the production schema.
        if failure_type is None:
            try:
                ProductSafetyAnalysis.model_validate(analysis)
            except ValidationError as ve:
                failure_type = "schema_invalid"
                logger.warning("schema_invalid for %s/%s: %s errors",
                               config_name, product_id, ve.error_count())

        if _ls_rt is not None:
            try:
                _ls_rt.add_metadata({
                    "failure_type": failure_type or "ok",
                    "model": (result.notes.get("model") if result and result.notes else ""),
                })
            except Exception:
                pass

    harm_score = HarmScoreCalculator.calculate(analysis) if analysis else 0

    # Finalize token tracking.
    summary = token_tracker.finish_analysis()
    total_cost = summary.total_cost if summary else 0.0
    try:
        budget.add(total_cost)
    except BudgetExceeded:
        # Re-raise — the caller halts the run.
        raise

    correctness = _compute_correctness(analysis, ground_truth.get(product_id, {}), harm_score)
    divergence = _compute_divergence(analysis, reference_index.get(product_id), harm_score)

    metrics = RunMetrics(
        config_name=config_name,
        product_id=product_id,
        run_idx=run_idx,
        model_id=(result.notes.get("model") if result and result.notes else ""),
        input_tokens=summary.total_input_tokens if summary else 0,
        output_tokens=summary.total_output_tokens if summary else 0,
        cache_read_tokens=summary.total_cache_read_tokens if summary else 0,
        cache_creation_tokens=summary.total_cache_creation_tokens if summary else 0,
        total_cost_usd=total_cost,
        cache_hit_rate=summary.aggregate_cache_hit_rate if summary else None,
        search_count=summary.search_count if summary else 0,
        search_cost_usd=summary.search_cost if summary else 0.0,
        total_latency_ms=total_latency_ms,
        per_phase_latency_ms=tracer.trace.per_phase_latency_ms(),
        tool_call_count=len(tracer.trace.tool_calls),
        harm_score=harm_score,
        failure_type=failure_type,
        retry_count=retry_count,
        **correctness,
        **divergence,
    )

    # Persist artifacts.
    run_dir = output_dir / "runs" / config_name / product_id / f"run{run_idx}"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "analysis.json").write_text(json.dumps(analysis, indent=2, default=str))
    (run_dir / "trace.json").write_text(tracer.to_json())
    (run_dir / "metrics.json").write_text(json.dumps(asdict(metrics), indent=2, default=str))
    (run_dir / "token_summary.json").write_text(
        json.dumps(summary.to_dict() if summary else {}, indent=2, default=str)
    )

    return metrics


async def run_eval(
    *,
    configs: List[str],
    dataset_path: Path,
    ground_truth_path: Path,
    output_dir: Path,
    runs_per_product: Dict[str, int],
    max_cost_usd: float,
    resume: bool = False,
    anthropic_concurrency: int = 3,
    cohere_concurrency: int = 3,
    use_supabase: bool = True,
) -> Dict[str, Any]:
    """Top-level eval loop. Returns a summary dict."""
    from src.infrastructure.search_tool_service import SearchToolService
    from src.infrastructure.database import db as _db

    output_dir.mkdir(parents=True, exist_ok=True)
    dataset = _load_dataset(dataset_path)
    ground_truth = _load_ground_truth(ground_truth_path)

    # Knowledge bases: load once, freeze snapshot.
    supabase_client = None
    allergen_db: List[Dict[str, Any]] = []
    pfas_db: List[Dict[str, Any]] = []
    if use_supabase and _db.is_available:
        supabase_client = _db.client
        allergen_db = await _db.get_all_allergens()
        pfas_db = await _db.get_all_pfas()
    else:
        kb_path = dataset_path.parent / "kb_snapshot.json"
        if kb_path.exists():
            snap = json.loads(kb_path.read_text())
            allergen_db = snap.get("allergens", [])
            pfas_db = snap.get("pfas", [])
        else:
            logger.warning("No Supabase and no kb_snapshot.json — KBs will be empty")

    # Shared search service.
    search_service = SearchToolService(supabase_client=supabase_client)

    # Checkpoint.
    benchmark_root = Path(__file__).parent
    config_hash = compute_config_hash(
        benchmark_root / "configs" / "prompts.py",
        benchmark_root / "configs" / "tool_schemas.py",
        dataset_path,
        ground_truth_path,
    )
    ckpt = Checkpoint.load_or_create(
        output_dir / ".checkpoint.json", config_hash=config_hash, resume=resume
    )
    install_signal_flush(ckpt)

    budget = BudgetTracker(max_cost_usd=max_cost_usd, spent_usd=ckpt.spent_usd)

    # Reference = config 1's analysis (computed lazily — populated as runs land).
    reference_index: Dict[str, Dict[str, Any]] = {}
    reference_config = "claude_agentsdk_async_cached"

    # Build runner instances once.
    runners = {name: get_runner(name) for name in configs}

    async def _bounded_run(config_name, product_row, run_idx):
        provider = _provider_for(config_name)
        sem = _get_semaphore(provider, anthropic_concurrency, cohere_concurrency)
        async with sem:
            return await _run_one(
                config_name=config_name,
                runner_obj=runners[config_name],
                product_row=product_row,
                run_idx=run_idx,
                allergen_db=allergen_db,
                pfas_db=pfas_db,
                search_service=search_service,
                supabase_client=supabase_client,
                output_dir=output_dir,
                budget=budget,
                ground_truth=ground_truth,
                reference_index=reference_index,
            )

    all_metrics: List[RunMetrics] = []
    # Order: Tier A first (those with ground truth), then Tier B.
    a_first = sorted(dataset, key=lambda r: (r["product_id"] not in ground_truth, r["product_id"]))

    # Phase 1: Run the reference config across all products serially so the
    # reference baseline is populated before divergence is measured.
    if reference_config in configs:
        for product_row in a_first:
            n = runs_per_product.get(product_row["product_id"],
                                     runs_per_product.get("_default", 1))
            for r in range(n):
                if ckpt.is_completed(reference_config, product_row["product_id"], r):
                    continue
                try:
                    m = await _bounded_run(reference_config, product_row, r)
                except BudgetExceeded as be:
                    logger.error("Budget exceeded: %s", be)
                    return _summarize(all_metrics, ckpt)
                all_metrics.append(m)
                ckpt.mark_completed(reference_config, product_row["product_id"], r, m.total_cost_usd)
                # Cache the run-0 result as the reference for this product.
                if r == 0 and m.failure_type is None:
                    reference_index[product_row["product_id"]] = {
                        "analysis": json.loads(
                            (output_dir / "runs" / reference_config / product_row["product_id"]
                             / f"run{r}" / "analysis.json").read_text()
                        ),
                        "harm_score": m.harm_score,
                    }

    # Phase 2: Run remaining configs in parallel (per-provider semaphore).
    other_configs = [c for c in configs if c != reference_config]
    for config_name in other_configs:
        tasks = []
        for product_row in a_first:
            n = runs_per_product.get(product_row["product_id"],
                                     runs_per_product.get("_default", 1))
            for r in range(n):
                if ckpt.is_completed(config_name, product_row["product_id"], r):
                    continue
                tasks.append((config_name, product_row, r))
        results = await asyncio.gather(
            *[_bounded_run(c, p, r) for c, p, r in tasks], return_exceptions=True
        )
        for (c, p, r), out in zip(tasks, results):
            if isinstance(out, BudgetExceeded):
                logger.error("Budget exceeded during %s: %s", c, out)
                return _summarize(all_metrics, ckpt)
            if isinstance(out, Exception):
                logger.error("Run %s/%s/run%s failed: %s", c, p["product_id"], r, out)
                continue
            all_metrics.append(out)
            ckpt.mark_completed(c, p["product_id"], r, out.total_cost_usd)

    return _summarize(all_metrics, ckpt)


def _summarize(metrics: List[RunMetrics], ckpt: Checkpoint) -> Dict[str, Any]:
    return {
        "runs": [asdict(m) for m in metrics],
        "spent_usd": ckpt.spent_usd,
        "completed_count": len(ckpt.completed),
    }


__all__ = ["run_eval"]
