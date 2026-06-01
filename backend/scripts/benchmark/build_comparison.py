#!/usr/bin/env python3
"""Render a Ruh-styled, 5-column side-by-side comparison of the agent-config
benchmark runs. Reads the run outputs + ground truth, computes accuracy on the
labelled products, and writes a self-contained HTML file (no JS deps).

Usage:  python -m scripts.benchmark.build_comparison [--output PATH] [--runs-dir DIR]
"""
from __future__ import annotations

import argparse
import glob
import json
import os
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]

# ---- Ruh brand palette (from ruh-brand-guide.md / extension utils.ts) --------
CREAM = "#FFFBF5"; LINEN = "#F5F0E8"; SAND = "#E8DCC8"; SAGE = "#A8B89F"
TAUPE = "#C9B5A0"; CHARCOAL = "#3A3633"; GRAY = "#6B6560"
SAFE = "#9BB88F"; CAUTION = "#D4A574"; ALERT = "#c45c4a"; SEVERE = "#a63d2d"; MINOR = "#b8c9a8"

CONFIG_META = {
    "claude_agentsdk_async_cached":     ("Claude", "Agent SDK · async · 1h cache"),
    "cohere_asyncv2_cached":            ("Cohere", "Async v2 · cache"),
    "claude_langgraph12_cached":        ("Claude", "LangGraph 1.2 · cache"),
    "cohere_langgraph12":               ("Cohere", "LangGraph 1.2"),
    "claude_cohere_coordinated_cached": ("Claude + Cohere", "Coordinated · cache"),
}

# ---- Metric tooltips: exact definition + impact on app reliability -----------
TIPS = {
    "composite": "A single 0–100 roll-up of the four measured signals below: "
                 "<b>30%</b> valid-output rate + <b>25%</b> PFAS F1 + <b>25%</b> allergen F1 + "
                 "<b>20%</b> harm-score calibration. <b>Impact:</b> higher means the app more often "
                 "returns a result that is well-formed, correctly grounded, and correctly "
                 "calibrated — the working definition of a trustworthy analysis.",
    "allg_rec": "Recall = of the allergens truly present in labelled products, the fraction the "
                "agent found — TP ÷ (TP+FN). <b>Impact:</b> low recall means the app misses real "
                "allergens (e.g. peanuts in peanut butter) — a dangerous miss for a safety tool.",
    "allg_prec": "Precision = of the allergens the agent reported, the fraction actually present — "
                 "TP ÷ (TP+FP). <b>Impact:</b> low precision means false alarms; the app flags "
                 "allergens that aren't there, over-scaring users and eroding trust. Names must "
                 "match the knowledge base exactly to count.",
    "valid": "Share of the 15 analyses whose output conforms to the app's "
             "<i>ProductSafetyAnalysis</i> schema (required fields, types, enums). "
             "<b>Impact:</b> a non-conforming result is rejected by the backend and never reaches "
             "the user — it surfaces as a failed or empty analysis card.",
    "schema_fail": "Runs whose JSON parsed but failed strict Pydantic validation against the "
                   "production schema. <b>Impact:</b> each is an analysis the backend throws out — "
                   "a hard failure from the user's point of view.",
    "harm_cal": "Of the labelled products with a known expected harm-score range, how many "
                "scored inside that range. <b>Impact:</b> the harm score is the headline donut the "
                "user sees — miscalibration means the app shows a misleading safety rating "
                "(false alarm or false reassurance).",
    "pfas_rec": "Recall = of the PFAS truly present in labelled products, the fraction the agent "
                "found — TP ÷ (TP+FN). <b>Impact:</b> low recall means the app misses real hazards "
                "(e.g. fails to warn about PTFE). For a safety tool this is the most dangerous error.",
    "pfas_prec": "Precision = of the PFAS the agent reported, the fraction actually present — "
                 "TP ÷ (TP+FP). <b>Impact:</b> low precision means false alarms; the app flags PFAS "
                 "that aren't there, over-scaring users and eroding trust.",
    "latency": "Mean wall-clock seconds per analysis (prompt build + search/tool loop + model "
               "calls). <b>Impact:</b> the extension analyses live on the product page — slow "
               "configs hurt UX and risk timing out before the user sees a result.",
    "cost": "Total model + search-API spend across all 15 runs for this config. <b>Impact:</b> "
            "per-analysis cost decides whether the free tier and credit economics stay sustainable "
            "as usage scales.",
    "tokens": "Total input / output tokens over the 15 runs (input = prompt + knowledge base + "
              "tool results; output = the generated analysis). <b>Impact:</b> tokens are the main "
              "cost and latency driver, and oversized inputs risk hitting the model's context limit.",
    "m_harm": "The 0–100 harm score this config produced for the product, colored by the app's risk "
              "bands (≤20 safe → &gt;80 severe). <b>Impact:</b> this is the exact number the user's "
              "donut would show.",
    "m_range": "Whether that harm score landed inside the ground-truth expected range for a labelled "
               "product (✓ in range / ✗ out of range). <b>Impact:</b> ✗ means the app would show the "
               "wrong safety level for a product whose true level is known.",
    "m_pfas": "PFAS compounds this config reported as detected for the product. <b>Impact:</b> these "
              "are the hazard warnings the user would see — missing or spurious chips both mislead.",
    "m_schema": "This run's output failed schema validation, so the backend would reject it. "
                "<b>Impact:</b> the user would get a failed analysis for this product.",
}


def wrap_tip(label, key):
    """Wrap visible label html in a hover/focus tooltip carrying TIPS[key]."""
    return f'<span class="tip" tabindex="0">{label}<span class="ttip">{TIPS[key]}</span></span>'


def harm_color(score):
    if score is None: return GRAY
    if score <= 20: return SAFE
    if score <= 40: return MINOR
    if score <= 60: return CAUTION
    if score <= 80: return ALERT
    return SEVERE


def score_color(pct):
    if pct >= 75: return SAFE
    if pct >= 60: return MINOR
    if pct >= 45: return CAUTION
    return ALERT


# Re-validate analyses against the CURRENT schema so schema fixes flow into the
# report without a re-run. Optional — falls back to baked failure_type if absent.
try:
    from src.domain.extraction_schemas import ProductSafetyAnalysis as _SCHEMA
except Exception:  # pragma: no cover
    _SCHEMA = None


def _confusion(detected, expected):
    """Case-insensitive exact-match confusion counts (mirrors metrics.confusion)."""
    sd = {x.strip().lower() for x in detected if x}
    se = {x.strip().lower() for x in expected if x}
    return len(sd & se), len(sd - se), len(se - sd)


def _prf(tp, fp, fn):
    p = tp / (tp + fp) if (tp + fp) else None
    r = tp / (tp + fn) if (tp + fn) else None
    f = (2 * p * r / (p + r)) if (p and r) else 0.0
    return p, r, f


def aggregate(runs_dir: Path, datasets: Path):
    gt = {r["product_id"]: r for r in json.loads((datasets / "ground_truth_v1.json").read_text())}
    ds = json.loads((datasets / "v1.json").read_text())
    ds = ds if isinstance(ds, list) else ds.get("products", [])
    pname = {p["product_id"]: p["product_data"].get("product_name", p["product_id"]) for p in ds}

    configs = {}
    for cfgdir in sorted(glob.glob(str(runs_dir / "*"))):
        cfg = os.path.basename(cfgdir)
        if cfg not in CONFIG_META:
            continue
        a = dict(n=0, ok=0, schema_invalid=0, lat=[], cost=0.0, in_tok=0, out_tok=0,
                 a_tp=0, a_fp=0, a_fn=0, p_tp=0, p_fp=0, p_fn=0, harm_ok=0, harm_n=0,
                 per_product={})
        for mp in glob.glob(f"{cfgdir}/*/run*/metrics.json"):
            d = json.loads(Path(mp).read_text()); pid = d["product_id"]; a["n"] += 1
            ft = d.get("failure_type")
            if d.get("total_latency_ms"): a["lat"].append(d["total_latency_ms"] / 1000)
            a["cost"] += d.get("total_cost_usd", 0) or 0
            a["in_tok"] += d.get("input_tokens", 0) or 0
            a["out_tok"] += d.get("output_tokens", 0) or 0
            # Correctness + validity recomputed FRESH from the saved analysis against the
            # current schema/GT, so schema relaxations and GT edits flow into the report
            # without a re-run (metrics.json baked these against earlier versions).
            gtp = gt.get(pid, {})
            harm = d.get("harm_score")
            det_al, det_pf, concerns = [], [], 0
            ap = mp.replace("metrics.json", "analysis.json")
            aj = json.loads(Path(ap).read_text()) if os.path.exists(ap) else None
            if aj is not None:
                det_al = [x.get("name", "") for x in aj.get("allergens_detected", [])]
                det_pf = [x.get("name", "") for x in aj.get("pfas_detected", [])]
                concerns = len(aj.get("other_concerns", []))
            # validity: re-validate against the current schema; non-schema run failures
            # (api_error, runner_exception) stay failures.
            if ft in (None, "schema_invalid") and aj is not None and _SCHEMA is not None:
                try:
                    _SCHEMA.model_validate(aj); valid = True
                except Exception:
                    valid = False
            else:
                valid = (ft is None)
            if valid:
                a["ok"] += 1
            elif ft in (None, "schema_invalid"):
                a["schema_invalid"] += 1
            atp, afp, afn = _confusion(det_al, gtp.get("expected_allergens", []))
            ptp, pfp, pfn = _confusion(det_pf, gtp.get("expected_pfas", []))
            a["a_tp"] += atp; a["a_fp"] += afp; a["a_fn"] += afn
            a["p_tp"] += ptp; a["p_fp"] += pfp; a["p_fn"] += pfn
            hr = gtp.get("expected_harm_score_range")
            in_range = None
            if hr and len(hr) == 2 and harm is not None:
                a["harm_n"] += 1
                in_range = hr[0] <= harm <= hr[1]
                if in_range: a["harm_ok"] += 1
            a["per_product"][pid] = dict(
                allergens=det_al, pfas=det_pf, harm=harm, valid=valid,
                labelled=(pid in gt), concerns=concerns, in_range=in_range)
        # derived
        a["avg_lat"] = sum(a["lat"]) / len(a["lat"]) if a["lat"] else 0
        a["valid_rate"] = a["ok"] / a["n"] if a["n"] else 0
        a["pfas_prec"], a["pfas_rec"], a["pfas_f1"] = _prf(a["p_tp"], a["p_fp"], a["p_fn"])
        a["allg_prec"], a["allg_rec"], a["allg_f1"] = _prf(a["a_tp"], a["a_fp"], a["a_fn"])
        a["harm_cal"] = a["harm_ok"] / a["harm_n"] if a["harm_n"] else 0
        # Composite now weights both detection axes since allergen GT is populated.
        a["composite"] = round(100 * (0.30 * a["valid_rate"] + 0.25 * a["pfas_f1"]
                                      + 0.25 * a["allg_f1"] + 0.20 * a["harm_cal"]))
        configs[cfg] = a
    return configs, gt, pname


def donut(pct, color, size=104, stroke=11):
    import math
    r = (size - stroke) / 2; c = 2 * math.pi * r
    off = c * (1 - pct / 100)
    cx = size / 2
    return f"""<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}" class="donut">
      <circle cx="{cx}" cy="{cx}" r="{r}" fill="none" stroke="{SAND}" stroke-width="{stroke}"/>
      <circle cx="{cx}" cy="{cx}" r="{r}" fill="none" stroke="{color}" stroke-width="{stroke}"
        stroke-linecap="round" stroke-dasharray="{c:.1f}" stroke-dashoffset="{off:.1f}"
        transform="rotate(-90 {cx} {cx})"/>
      <text x="50%" y="50%" text-anchor="middle" dy="-2" class="donut-num">{pct}</text>
      <text x="50%" y="50%" text-anchor="middle" dy="15" class="donut-lbl">/ 100</text>
    </svg>"""


def stat(label, value, color=CHARCOAL, sub="", tipkey=None):
    subhtml = f'<span class="stat-sub">{sub}</span>' if sub else ""
    lab = wrap_tip(label, tipkey) if tipkey else label
    return (f'<div class="stat"><div class="stat-label">{lab}</div>'
            f'<div class="stat-value" style="color:{color}">{value}{subhtml}</div></div>')


def bar(pct, color):
    return (f'<div class="bar"><div class="bar-fill" style="width:{pct*100:.0f}%;'
            f'background:{color}"></div></div>')


def build(configs, gt, pname):
    order = sorted(configs, key=lambda c: configs[c]["composite"], reverse=True)
    best = order[0]
    total_cost = sum(configs[c]["cost"] for c in configs)

    cols = []
    for rank, cfg in enumerate(order):
        a = configs[cfg]; provider, arch = CONFIG_META[cfg]
        comp = a["composite"]; col = score_color(comp)
        winner = '<div class="ribbon">★ top composite</div>' if cfg == best else ""
        prec = f'{a["pfas_prec"]*100:.0f}%' if a["pfas_prec"] is not None else "—"
        rec = f'{a["pfas_rec"]*100:.0f}%' if a["pfas_rec"] is not None else "—"
        pfp = a["p_fp"]
        fp_note = f'<span class="stat-sub">{pfp} false pos.</span>' if pfp else '<span class="stat-sub" style="color:'+SAFE+'">clean</span>'
        aprec = f'{a["allg_prec"]*100:.0f}%' if a["allg_prec"] is not None else "—"
        arec = f'{a["allg_rec"]*100:.0f}%' if a["allg_rec"] is not None else "—"
        afp = a["a_fp"]
        a_fp_note = f'<span class="stat-sub">{afp} false pos.</span>' if afp else '<span class="stat-sub" style="color:'+SAFE+'">clean</span>'
        cols.append(f"""
        <div class="card {'winner' if cfg==best else ''}">
          {winner}
          <div class="prov">{provider}</div>
          <div class="arch">{arch}</div>
          <div class="donut-wrap">{donut(comp, col)}</div>
          <div class="comp-cap">{wrap_tip("composite accuracy", "composite")}</div>

          <div class="section-h">Reliability</div>
          {stat("Valid outputs", f'{a["ok"]}/{a["n"]}', score_color(a["valid_rate"]*100), tipkey="valid")}
          {bar(a["valid_rate"], score_color(a["valid_rate"]*100))}
          <div class="muted">{wrap_tip(f'{a["schema_invalid"]} failed schema validation', "schema_fail")}</div>

          <div class="section-h">Accuracy <span class="tag">{a["harm_n"]} labelled</span></div>
          {stat("Harm-score calibration", f'{a["harm_ok"]}/{a["harm_n"]}', score_color(a["harm_cal"]*100), sub="in expected range", tipkey="harm_cal")}
          {bar(a["harm_cal"], score_color(a["harm_cal"]*100))}
          <div class="row2">
            {stat("Allergen recall", arec, score_color((a["allg_rec"] or 0)*100), tipkey="allg_rec")}
            {stat("Allergen precision", aprec, score_color((a["allg_prec"] or 0)*100), tipkey="allg_prec")}
          </div>
          <div class="muted">allergens · {a_fp_note}</div>
          <div class="row2">
            {stat("PFAS recall", rec, SAFE if (a["pfas_rec"] or 0)>=0.99 else CAUTION, tipkey="pfas_rec")}
            {stat("PFAS precision", prec, score_color((a["pfas_prec"] or 0)*100), tipkey="pfas_prec")}
          </div>
          <div class="muted">PFAS · {fp_note}</div>

          <div class="section-h">Cost &amp; speed</div>
          <div class="row2">
            {stat("Avg latency", f'{a["avg_lat"]:.0f}s', tipkey="latency")}
            {stat("Total cost", f'${a["cost"]:.2f}', tipkey="cost")}
          </div>
          {stat("Tokens (in / out)", f'{a["in_tok"]//1000}k / {a["out_tok"]//1000}k', GRAY, tipkey="tokens")}
        </div>""")

    # ---- per-product matrix (rows = products, cols = configs) ----
    prod_ids = sorted(pname, key=lambda p: (p not in gt, p))  # labelled first
    head_cells = "".join(
        f'<th><div class="th-prov">{CONFIG_META[c][0]}</div>'
        f'<div class="th-arch">{CONFIG_META[c][1].split(" · ")[0]}</div></th>' for c in order)
    rows = []
    for pid in prod_ids:
        labelled = pid in gt
        gtp = gt.get(pid, {})
        gt_pfas = ", ".join(gtp.get("expected_pfas", [])) or "—"
        gt_al = ", ".join(gtp.get("expected_allergens", [])) or "—"
        exp_al = {x.strip().lower() for x in gtp.get("expected_allergens", [])}
        hr = gtp.get("expected_harm_score_range")
        gt_tag = (f'<span class="gt-pill">GT · allg: {gt_al} · PFAS: {gt_pfas} · harm {hr[0]}–{hr[1]}</span>'
                  if labelled else '<span class="gt-pill none">no ground truth</span>')
        cells = []
        for c in order:
            d = configs[c]["per_product"].get(pid, {})
            harm = d.get("harm"); hc = harm_color(harm)
            pf = d.get("pfas") or []
            pf_html = (" ".join(f'<span class="chip">{x}</span>' for x in pf) if pf
                       else '<span class="chip empty">none</span>')
            al = d.get("allergens") or []
            # green = matches GT (true positive), red = false positive vs GT
            al_html = (" ".join(
                f'<span class="chip {"hit" if x.strip().lower() in exp_al else "fp"}">{x}</span>'
                for x in al) if al else '')
            al_div = f'<div class="al">{al_html}</div>' if al_html else ''
            valid = d.get("valid")
            badge = '' if valid else '<span class="invalid">schema✗</span>'
            in_range = ""
            if labelled and harm is not None and hr:
                ok = hr[0] <= harm <= hr[1]
                in_range = f'<span class="rng {"ok" if ok else "no"}">{"✓" if ok else "✗"} range</span>'
            cells.append(
                f'<td><span class="harm-dot" style="background:{hc}">{harm if harm is not None else "—"}</span>'
                f'{in_range}{badge}<div class="pf">{pf_html}</div>{al_div}</td>')
        rows.append(
            f'<tr class="{"lab" if labelled else "unlab"}"><td class="pcell">'
            f'<div class="pname">{pname[pid]}</div>{gt_tag}</td>{"".join(cells)}</tr>')

    matrix = f"""<table class="matrix">
      <thead><tr><th class="corner">Product</th>{head_cells}</tr></thead>
      <tbody>{"".join(rows)}</tbody></table>"""

    legend = (
        '<div class="legend">'
        + '<span class="legend-lbl">What each cell means — hover:</span>'
        + wrap_tip(f'<span class="harm-dot mini" style="background:{SAFE}">0–100</span> harm score', "m_harm")
        + wrap_tip('<span class="rng ok">✓ range</span>', "m_range")
        + wrap_tip('<span class="chip">PFAS chip</span>', "m_pfas")
        + wrap_tip('<span class="invalid">schema✗</span>', "m_schema")
        + '</div>'
    )
    ls_proj = os.environ.get("LANGSMITH_PROJECT")
    if ls_proj:
        langsmith = (f'<div>🔍 Reasoning traces in '
                     f'<a href="https://smith.langchain.com" target="_blank" rel="noopener" '
                     f'style="color:#6f8f63;font-weight:600">LangSmith</a> · project '
                     f'<b>{ls_proj}</b> <span class="stat-sub">(filter by config tag for the '
                     f'turn-by-turn reason→act→observe loop)</span></div>')
    else:
        langsmith = ('<div>🔍 <a href="https://smith.langchain.com" target="_blank" rel="noopener" '
                     'style="color:#6f8f63;font-weight:600">LangSmith</a> reasoning traces '
                     '<span class="stat-sub">(set LANGSMITH_PROJECT to label the link)</span></div>')
    return PAGE.format(cards="".join(cols), matrix=matrix, legend=legend, langsmith=langsmith,
                       total_cost=f"{total_cost:.2f}", n_cfg=len(order))


PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ruh · agent-config benchmark</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Infant:ital,wght@1,500;1,600&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
:root{{--cream:#FFFBF5;--linen:#F5F0E8;--sand:#E8DCC8;--sage:#A8B89F;--taupe:#C9B5A0;
--charcoal:#3A3633;--gray:#6B6560;--safe:#9BB88F;--caution:#D4A574;--alert:#c45c4a;}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Inter',system-ui,sans-serif;background:var(--cream);color:var(--charcoal);
line-height:1.5;padding:32px 28px 60px}}
.logo{{font-family:'Cormorant Infant',serif;font-style:italic;font-weight:600;font-size:42px;
letter-spacing:.06em;color:var(--taupe);line-height:1}}
header{{max-width:1500px;margin:0 auto 26px}}
h1{{font-size:22px;font-weight:600;margin:6px 0 4px}}
.sub{{color:var(--gray);font-size:14px}}
.meta-bar{{display:flex;gap:22px;flex-wrap:wrap;margin-top:14px;padding:12px 18px;
background:var(--linen);border-radius:14px;border:1px solid var(--sand)}}
.meta-bar div{{font-size:13px;color:var(--gray)}}
.meta-bar b{{color:var(--charcoal);font-weight:600}}
.grid{{max-width:1500px;margin:0 auto;display:grid;grid-template-columns:repeat({n_cfg},1fr);
gap:16px;align-items:start}}
@media(max-width:1100px){{.grid{{grid-auto-flow:column;grid-template-columns:none;
grid-auto-columns:300px;overflow-x:auto;padding-bottom:10px}}}}
.card{{background:var(--linen);border:1px solid var(--sand);border-radius:18px;padding:20px 18px;
position:relative;box-shadow:0 1px 3px rgba(58,54,51,.05)}}
.card.winner{{border:1.5px solid var(--sage);box-shadow:0 6px 22px rgba(168,184,159,.28)}}
.ribbon{{position:absolute;top:-11px;left:50%;transform:translateX(-50%);background:var(--sage);
color:#2d3a28;font-size:11px;font-weight:600;padding:3px 12px;border-radius:20px;white-space:nowrap}}
.prov{{font-size:17px;font-weight:700;margin-top:4px}}
.arch{{font-size:12px;color:var(--gray);margin-bottom:8px;min-height:30px}}
.donut-wrap{{display:flex;justify-content:center;margin:4px 0 2px}}
.donut-num{{font-size:30px;font-weight:700;fill:var(--charcoal);font-family:'Inter'}}
.donut-lbl{{font-size:10px;fill:var(--gray);font-family:'Inter'}}
.comp-cap{{text-align:center;font-size:11px;color:var(--gray);text-transform:uppercase;
letter-spacing:.08em;margin-bottom:6px}}
.section-h{{font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.07em;
color:var(--gray);margin:16px 0 8px;border-top:1px solid var(--sand);padding-top:12px;
display:flex;justify-content:space-between;align-items:center}}
.tag{{background:var(--sand);color:var(--gray);font-size:9px;padding:2px 7px;border-radius:10px;
letter-spacing:.04em}}
.stat{{display:flex;justify-content:space-between;align-items:baseline;margin:5px 0}}
.stat-label{{font-size:13px;color:var(--gray)}}
.stat-value{{font-size:16px;font-weight:600}}
.stat-sub{{font-size:10px;color:var(--gray);font-weight:400;margin-left:5px}}
.row2{{display:flex;gap:14px}}.row2 .stat{{flex:1;flex-direction:column;align-items:flex-start;gap:1px}}
.bar{{height:6px;background:var(--sand);border-radius:4px;overflow:hidden;margin:3px 0 2px}}
.bar-fill{{height:100%;border-radius:4px}}
.muted{{font-size:11px;color:var(--gray);margin-top:4px}}
.section-title{{max-width:1500px;margin:42px auto 14px;font-size:18px;font-weight:600}}
.matrix{{max-width:1500px;margin:0 auto;border-collapse:separate;border-spacing:0;width:100%;
background:var(--linen);border:1px solid var(--sand);border-radius:16px;overflow:hidden;font-size:13px}}
.matrix th,.matrix td{{padding:11px 12px;text-align:left;border-bottom:1px solid var(--sand);
vertical-align:top}}
.matrix thead th{{background:var(--sand);position:sticky;top:0}}
.th-prov{{font-weight:700;font-size:13px}}.th-arch{{font-size:10px;color:var(--gray);font-weight:400}}
.corner{{font-weight:600}}
.pcell{{min-width:190px}}.pname{{font-weight:600;margin-bottom:4px}}
.gt-pill{{display:inline-block;font-size:10px;background:var(--sage);color:#2d3a28;padding:2px 8px;
border-radius:10px}}
.gt-pill.none{{background:var(--sand);color:var(--gray)}}
tr.unlab{{opacity:.72}}
.harm-dot{{display:inline-flex;align-items:center;justify-content:center;width:30px;height:30px;
border-radius:50%;color:#fff;font-weight:700;font-size:12px}}
.rng{{font-size:10px;margin-left:6px;font-weight:600}}
.rng.ok{{color:#6f8f63}}.rng.no{{color:var(--alert)}}
.invalid{{font-size:10px;color:var(--alert);margin-left:6px;font-weight:600}}
.pf,.al{{margin-top:6px;display:flex;flex-wrap:wrap;gap:3px}}
.al{{margin-top:3px}}
.chip{{font-size:10px;background:#e7d3c8;color:#7a4a36;padding:2px 7px;border-radius:8px}}
.chip.empty{{background:var(--sand);color:var(--gray)}}
.chip.hit{{background:#d4dbc9;color:#3f5536}}
.chip.fp{{background:#efcfc6;color:#8a3b28}}
.foot{{max-width:1500px;margin:22px auto 0;font-size:11px;color:var(--gray);line-height:1.7}}
.foot code{{background:var(--linen);padding:1px 5px;border-radius:4px}}
/* tooltips */
.tip{{position:relative;cursor:help;border-bottom:1px dotted var(--taupe);outline:none}}
.tip::after{{content:"\\00a0\\24d8";font-size:.85em;color:var(--taupe)}}
.tip .ttip{{visibility:hidden;opacity:0;position:absolute;bottom:calc(100% + 9px);left:50%;
transform:translateX(-50%);width:236px;background:var(--charcoal);color:#fff;padding:10px 12px;
border-radius:10px;font-size:11px;line-height:1.5;font-weight:400;text-transform:none;
letter-spacing:normal;text-align:left;z-index:80;box-shadow:0 8px 26px rgba(58,54,51,.3);
transition:opacity .12s ease;pointer-events:none;white-space:normal}}
.tip .ttip b{{color:var(--sand)}}.tip .ttip i{{color:var(--sage);font-style:normal}}
.tip .ttip::after{{content:"";position:absolute;top:100%;left:50%;transform:translateX(-50%);
border:6px solid transparent;border-top-color:var(--charcoal)}}
.tip:hover .ttip,.tip:focus .ttip{{visibility:visible;opacity:1}}
/* edge columns: align tooltip inward so it never clips off-screen */
.grid>.card:first-child .ttip{{left:0;right:auto;transform:none}}
.grid>.card:first-child .ttip::after{{left:22px;right:auto;transform:none}}
.grid>.card:last-child .ttip{{left:auto;right:0;transform:none}}
.grid>.card:last-child .ttip::after{{left:auto;right:22px;transform:none}}
.legend .ttip{{left:0;right:auto;transform:none}}
.legend .ttip::after{{left:22px;right:auto;transform:none}}
.legend{{max-width:1500px;margin:0 auto 12px;display:flex;gap:18px;flex-wrap:wrap;align-items:center;
font-size:12px;color:var(--gray);padding:10px 16px;background:var(--linen);border:1px solid var(--sand);
border-radius:12px}}
.legend-lbl{{font-weight:600;color:var(--charcoal)}}
.legend .tip{{border-bottom:none;display:inline-flex;align-items:center;gap:5px}}
.harm-dot.mini{{width:auto;height:auto;padding:2px 7px;border-radius:9px;font-size:11px}}
</style></head><body>
<header>
  <div class="logo">ruh</div>
  <h1>Agent-config benchmark — side by side</h1>
  <div class="sub">5 agent configurations · 15 products · grounded against local knowledge base (32 allergens, 75 PFAS)</div>
  <div class="meta-bar">
    <div>Mode <b>smoke</b> · 1 run/product</div>
    <div>Total spend <b>${total_cost}</b></div>
    <div>Detection scored on <b>15 labelled products</b></div>
    <div>Composite = <b>30% validity + 25% PFAS&nbsp;F1 + 25% allergen&nbsp;F1 + 20% harm calibration</b></div>
    {langsmith}
  </div>
</header>
<div class="grid">{cards}</div>
<div class="section-title">Per-product results</div>
{legend}
{matrix}
<div class="foot">
  <b>How to read this.</b> The donut is a composite of four measured signals, ranked best-first.
  <b>Accuracy is scored against ground truth (the answer key)</b>, now expanded to all 15 products —
  so allergen precision/recall is meaningful (8 products carry real allergen labels: peanuts, milk,
  wheat, lanolin, etc.). Allergen names must match the knowledge base exactly to count.
  Correctness is recomputed fresh from each saved analysis against the current ground truth, so the
  report reflects whatever <code>ground_truth_v1.json</code> currently holds.
  Harm dot color follows the app's risk bands (≤20 safe → &gt;80 severe). Generated from
  <code>output/smoke/runs/</code>.
</div>
</body></html>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs-dir", type=Path, default=BACKEND / "scripts/benchmark/output/smoke/runs")
    ap.add_argument("--datasets", type=Path, default=BACKEND / "scripts/benchmark/datasets")
    ap.add_argument("--output", type=Path, default=BACKEND / "scripts/benchmark/output/comparison.html")
    args = ap.parse_args()
    configs, gt, pname = aggregate(args.runs_dir, args.datasets)
    html = build(configs, gt, pname)
    args.output.write_text(html)
    print(f"wrote {args.output}  ({len(html)//1024} KB, {len(configs)} configs)")


if __name__ == "__main__":
    main()
