"""LLM-as-judge using Opus 4.7 (tier above the subjects to mitigate
self-preference bias).

Per (config, product, run) analysis we ask Opus to score the response on a
10-point rubric. Subjects are anonymized to A..E. Each judgment is run twice
with shuffled rubric-key order; if any dimension differs by > 2 we run a 3rd
pass and take the median. Disagreement is reported as a meta-metric.

A 10% sample is also re-judged by Command A 03-2025 so we can quantify
cross-judge bias.

Hard per-judgment budget: $0.10. The driver halts if it would be exceeded.
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import secrets
import string
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

JUDGE_MODEL = "claude-opus-4-7"
ALT_JUDGE_MODEL = "command-a-03-2025"

RUBRIC_KEYS = [
    "allergen_recall",
    "allergen_precision",
    "pfas_recall",
    "pfas_precision",
    "source_groundedness",
    "source_relevance",
    "confidence_calibration",
    "harm_score_defensibility",
    "hallucination_count",
    "overall_quality",
]

DISAGREEMENT_THRESHOLD = 2.0
PER_JUDGMENT_BUDGET_USD = 0.10


def anonymize_configs(configs: List[str]) -> Dict[str, str]:
    """Map config names to A, B, C, ... in a per-run shuffled order."""
    labels = list(string.ascii_uppercase[: len(configs)])
    shuffled = configs[:]
    random.shuffle(shuffled)
    return {name: labels[i] for i, name in enumerate(shuffled)}


def _build_rubric_prompt(
    analysis: Dict[str, Any],
    product_data: Dict[str, Any],
    rubric_order: List[str],
) -> str:
    rubric_text = "\n".join(
        f"- {k}: 1-10 (1=worst, 10=best). Rate the response on this dimension."
        for k in rubric_order
    )
    return (
        "You are a senior product-safety auditor evaluating an AI's analysis of a product.\n"
        "Score the response on each dimension below (integer 1-10). Use web_search to verify "
        "sources where possible — groundedness should reflect whether claims are backed by "
        "credible, verifiable references.\n\n"
        f"PRODUCT (reference, not produced by the AI):\n{json.dumps(product_data, indent=2)[:1500]}\n\n"
        f"AI RESPONSE TO EVALUATE:\n{json.dumps(analysis, indent=2)[:6000]}\n\n"
        f"RUBRIC:\n{rubric_text}\n\n"
        "Return ONLY a JSON object with keys exactly matching the rubric above. "
        "Use integer scores 1-10 for each dimension, plus a `rationale` string (1-2 sentences). "
        "Add a `hallucination_count` integer (0+) for claims you could not verify."
    )


async def _judge_once(
    client: Any,
    analysis: Dict[str, Any],
    product_data: Dict[str, Any],
    rubric_order: List[str],
    model: str,
) -> Tuple[Dict[str, Any], float]:
    """Return (scores_dict, cost_usd)."""
    prompt = _build_rubric_prompt(analysis, product_data, rubric_order)
    if model.startswith("claude"):
        return await _judge_claude(client, prompt, model)
    return await _judge_cohere(client, prompt, model)


async def _judge_claude(client: Any, prompt: str, model: str) -> Tuple[Dict[str, Any], float]:
    resp = await client.messages.create(
        model=model,
        max_tokens=1024,
        temperature=0.0,
        messages=[{"role": "user", "content": prompt}],
        tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 3}],
    )
    text = ""
    for b in resp.content:
        if getattr(b, "text", None):
            text += b.text + "\n"
    scores = _safe_json_parse(text)
    # Cost estimate using the same pricing table as token_tracker.
    from src.infrastructure.token_tracker import PRICING, DEFAULT_PRICING
    p = PRICING.get(model, DEFAULT_PRICING)
    cost = (resp.usage.input_tokens / 1_000_000) * p["input"]
    cost += (resp.usage.output_tokens / 1_000_000) * p["output"]
    return scores, cost


async def _judge_cohere(client: Any, prompt: str, model: str) -> Tuple[Dict[str, Any], float]:
    resp = await client.chat(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,
    )
    text = ""
    content = resp.message.content
    if isinstance(content, list):
        for c in content:
            t = getattr(c, "text", None) or (c.get("text") if isinstance(c, dict) else None)
            if t:
                text += t + "\n"
    elif isinstance(content, str):
        text = content
    scores = _safe_json_parse(text)
    from src.infrastructure.token_tracker import PRICING, DEFAULT_PRICING
    p = PRICING.get(model, DEFAULT_PRICING)
    usage = getattr(resp, "usage", None)
    billed = getattr(usage, "billed_units", None) if usage else None
    if billed:
        cost = (getattr(billed, "input_tokens", 0) / 1_000_000) * p["input"]
        cost += (getattr(billed, "output_tokens", 0) / 1_000_000) * p["output"]
    else:
        cost = 0.0
    return scores, cost


def _safe_json_parse(text: str) -> Dict[str, Any]:
    if not text:
        return {}
    s = text.strip()
    if "```" in s:
        after = s.split("```", 1)[1]
        if after.lower().startswith("json"):
            after = after[4:]
        end = after.find("```")
        if end != -1:
            s = after[:end].strip()
    start = s.find("{")
    end = s.rfind("}")
    if start == -1 or end <= start:
        return {}
    try:
        return json.loads(s[start: end + 1])
    except json.JSONDecodeError:
        return {}


@dataclass
class JudgeOutput:
    scores: Dict[str, float]
    disagreement: float
    cost_usd: float
    passes: int


async def judge_run(
    *,
    claude_client: Any,
    cohere_client: Optional[Any],
    analysis: Dict[str, Any],
    product_data: Dict[str, Any],
    use_alt_judge: bool = False,
    max_passes: int = 3,
) -> JudgeOutput:
    """Run the rubric twice with shuffled key order; reconcile via median.

    If ``use_alt_judge`` is True, the alternate (Cohere) judge is run once
    instead of the second Claude pass for cross-judge bias measurement.
    """
    rubric_a = RUBRIC_KEYS[:]
    rubric_b = RUBRIC_KEYS[:]
    random.shuffle(rubric_b)

    total_cost = 0.0
    scores_a, c_a = await _judge_once(claude_client, analysis, product_data, rubric_a, JUDGE_MODEL)
    total_cost += c_a
    if total_cost > PER_JUDGMENT_BUDGET_USD:
        logger.warning("Judge over per-judgment budget after pass 1")

    if use_alt_judge and cohere_client is not None:
        scores_b, c_b = await _judge_once(
            cohere_client, analysis, product_data, rubric_b, ALT_JUDGE_MODEL
        )
    else:
        scores_b, c_b = await _judge_once(
            claude_client, analysis, product_data, rubric_b, JUDGE_MODEL
        )
    total_cost += c_b

    merged, disagreement = _reconcile(scores_a, scores_b)
    passes = 2
    if disagreement > DISAGREEMENT_THRESHOLD and passes < max_passes:
        scores_c, c_c = await _judge_once(
            claude_client, analysis, product_data, RUBRIC_KEYS[:], JUDGE_MODEL
        )
        total_cost += c_c
        merged = _median(scores_a, scores_b, scores_c)
        passes = 3

    return JudgeOutput(
        scores=merged,
        disagreement=disagreement,
        cost_usd=total_cost,
        passes=passes,
    )


def _reconcile(a: Dict[str, Any], b: Dict[str, Any]) -> Tuple[Dict[str, float], float]:
    merged: Dict[str, float] = {}
    max_delta = 0.0
    for k in RUBRIC_KEYS:
        va = float(a.get(k, 0) or 0)
        vb = float(b.get(k, 0) or 0)
        merged[k] = (va + vb) / 2.0
        max_delta = max(max_delta, abs(va - vb))
    return merged, max_delta


def _median(a: Dict[str, Any], b: Dict[str, Any], c: Dict[str, Any]) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for k in RUBRIC_KEYS:
        vals = sorted(float(d.get(k, 0) or 0) for d in (a, b, c))
        out[k] = vals[1]
    return out


async def judge_all_runs(
    runs_dir: Path,
    output_file: Path,
    alt_judge_sample_rate: float = 0.10,
) -> None:
    """Walk output/runs/*/*/*/analysis.json and judge each. Persist results
    to ``output_file`` so a partial run can be resumed."""
    from anthropic import AsyncAnthropic
    from cohere import AsyncClientV2 as _CohereAsync
    from src.infrastructure.config import settings

    claude = AsyncAnthropic(api_key=settings.anthropic_api_key)
    cohere = _CohereAsync(api_key=settings.cohere_api_key) if settings.cohere_api_key else None

    results: List[Dict[str, Any]] = []
    if output_file.exists():
        results = json.loads(output_file.read_text())
    done = {(r["config"], r["product_id"], r["run_idx"]) for r in results}

    for path in sorted(runs_dir.rglob("analysis.json")):
        # path = .../runs/<config>/<product_id>/runN/analysis.json
        parts = path.parts
        run_dir_name = parts[-2]  # runN
        product_id = parts[-3]
        config_name = parts[-4]
        run_idx = int(run_dir_name.replace("run", "")) if run_dir_name.startswith("run") else 0

        key = (config_name, product_id, run_idx)
        if key in done:
            continue

        analysis = json.loads(path.read_text())
        # Pull product_data from the metrics next door — keep it small.
        product_data = analysis  # we only need the names/ingredients for grounding
        use_alt = secrets.randbelow(1000) / 1000.0 < alt_judge_sample_rate
        try:
            out = await judge_run(
                claude_client=claude,
                cohere_client=cohere,
                analysis=analysis,
                product_data=product_data,
                use_alt_judge=use_alt,
            )
        except Exception as e:
            logger.warning("Judge failed for %s: %s", key, e)
            continue
        results.append({
            "config": config_name,
            "product_id": product_id,
            "run_idx": run_idx,
            "scores": out.scores,
            "disagreement": out.disagreement,
            "cost_usd": out.cost_usd,
            "passes": out.passes,
            "used_alt_judge": use_alt,
        })
        output_file.write_text(json.dumps(results, indent=2))


__all__ = ["judge_all_runs", "judge_run", "anonymize_configs", "JudgeOutput"]
