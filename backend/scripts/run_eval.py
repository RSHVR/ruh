#!/usr/bin/env python3
"""Top-level CLI for the 5-config eval suite.

Examples
--------
    # ~$2 smoke run: 1 product × 5 configs × 1 run + report
    python -m scripts.run_eval --mode smoke --max-cost-usd 5

    # Full eval, hard $80 cap, resume on second invocation
    python -m scripts.run_eval --mode full --max-cost-usd 80 --resume

    # Tier A only (anchors with ground truth)
    python -m scripts.run_eval --mode tier-a --runs 5

    # Concurrency sub-benchmark (separate $15 budget)
    python -m scripts.run_eval --mode concurrency --max-cost-usd 20
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

# Repo path setup so `from src.infrastructure...` works.
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from scripts.benchmark import concurrency as _conc  # noqa: E402
from scripts.benchmark.budget import BudgetTracker  # noqa: E402
from scripts.benchmark.configs.registry import list_configs  # noqa: E402
from scripts.benchmark.runner import run_eval  # noqa: E402

logger = logging.getLogger("run_eval")


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def _parse() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Ruh 5-config agent eval")
    p.add_argument("--mode", choices=["smoke", "full", "tier-a", "tier-b", "concurrency", "report-only", "judge-only"],
                   default="smoke")
    p.add_argument("--configs", nargs="+", default=None,
                   help="Configs to run. Default: all 5.")
    p.add_argument("--runs", type=int, default=None,
                   help="Runs per product. Default: 5 (tier-a) or 3 (tier-b/full).")
    p.add_argument("--max-cost-usd", type=float, default=80.0)
    p.add_argument("--resume", action="store_true")
    p.add_argument("--force", action="store_true",
                   help="Skip the pre-flight cost-estimate check")
    p.add_argument("--anthropic-concurrency", type=int, default=3)
    p.add_argument("--cohere-concurrency", type=int, default=3)
    p.add_argument("--output", type=Path, default=None)
    p.add_argument("--dataset", type=Path,
                   default=BACKEND_DIR / "scripts/benchmark/datasets/v1.json")
    p.add_argument("--ground-truth", type=Path,
                   default=BACKEND_DIR / "scripts/benchmark/datasets/ground_truth_v1.json")
    p.add_argument("--no-supabase", action="store_true")
    p.add_argument("--judge", action="store_true",
                   help="After runs complete, judge each one with Opus 4.7")
    p.add_argument("--report", action="store_true", default=True,
                   help="Render Plotly HTML report at the end")
    p.add_argument("-v", "--verbose", action="store_true")
    return p.parse_args()


def _runs_per_product(args: argparse.Namespace, dataset_path: Path, gt_path: Path) -> dict:
    import json
    dataset = json.loads(dataset_path.read_text())
    gt_ids = set()
    if gt_path.exists():
        gt_ids = {row["product_id"] for row in json.loads(gt_path.read_text())}

    if args.mode == "smoke":
        return {"_default": 1}
    if args.mode == "tier-a":
        return {p["product_id"]: (args.runs or 5) for p in dataset if p["product_id"] in gt_ids} | {"_default": 0}
    if args.mode == "tier-b":
        return {p["product_id"]: (args.runs or 3) for p in dataset if p["product_id"] not in gt_ids} | {"_default": 0}
    # full
    return {
        **{p["product_id"]: (args.runs or 5) for p in dataset if p["product_id"] in gt_ids},
        **{p["product_id"]: (args.runs or 3) for p in dataset if p["product_id"] not in gt_ids},
    }


def _output_dir(mode: str, override: Path | None) -> Path:
    if override:
        return override
    return BACKEND_DIR / "scripts/benchmark/output" / mode


def _estimate_cost(runs_per_product: dict, configs: list[str], dataset_path: Path) -> float:
    """Rough pre-flight estimate: $0.20 per Claude-config analysis, $0.05 per
    Cohere-only-config analysis."""
    import json
    dataset = json.loads(dataset_path.read_text())
    total = 0.0
    for p in dataset:
        n = runs_per_product.get(p["product_id"], runs_per_product.get("_default", 0))
        if n <= 0:
            continue
        for c in configs:
            per = 0.05 if c.startswith("cohere_") else 0.20
            total += per * n
    return total


async def _main() -> int:
    args = _parse()
    _setup_logging(args.verbose)

    # Load .env so LANGSMITH_* (and other SDK vars) land in os.environ. Does not
    # override vars already exported in the shell (e.g. a local-Supabase override).
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except Exception:
        pass
    from scripts.benchmark.observability import tracing_enabled, project_name
    if tracing_enabled():
        logger.info("LangSmith tracing: ON (project=%s)", project_name() or "default")
    else:
        logger.info("LangSmith tracing: OFF (set LANGSMITH_TRACING=true in backend/.env)")

    configs = args.configs or list_configs()
    output_dir = _output_dir(args.mode, args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.mode == "report-only":
        from scripts.benchmark.report import build_report
        build_report(output_dir, judge_path=output_dir / "judge_results.json")
        return 0

    if args.mode == "judge-only":
        from scripts.benchmark.judge import judge_all_runs
        await judge_all_runs(
            runs_dir=output_dir / "runs",
            output_file=output_dir / "judge_results.json",
        )
        return 0

    if args.mode == "concurrency":
        result = await _conc.run_concurrency_benchmark(
            dataset_path=args.dataset,
            output_dir=output_dir,
        )
        logger.info("Concurrency complete: %s", list(result.keys()))
        return 0

    runs_per_product = _runs_per_product(args, args.dataset, args.ground_truth)
    estimated = _estimate_cost(runs_per_product, configs, args.dataset)
    BudgetTracker.preflight(
        estimated_total_cost=estimated,
        max_cost_usd=args.max_cost_usd,
        margin=1.4,
        force=args.force,
    )

    summary = await run_eval(
        configs=configs,
        dataset_path=args.dataset,
        ground_truth_path=args.ground_truth,
        output_dir=output_dir,
        runs_per_product=runs_per_product,
        max_cost_usd=args.max_cost_usd,
        resume=args.resume,
        anthropic_concurrency=args.anthropic_concurrency,
        cohere_concurrency=args.cohere_concurrency,
        use_supabase=not args.no_supabase,
    )
    logger.info("Eval complete: %s runs, $%.2f spent",
                summary.get("completed_count", 0), summary.get("spent_usd", 0.0))

    if args.judge:
        from scripts.benchmark.judge import judge_all_runs
        await judge_all_runs(
            runs_dir=output_dir / "runs",
            output_file=output_dir / "judge_results.json",
        )

    if args.report:
        from scripts.benchmark.report import build_report
        build_report(output_dir, judge_path=output_dir / "judge_results.json")

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
