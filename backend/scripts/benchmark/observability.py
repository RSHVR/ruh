"""LangSmith root-trace helper for the eval harness.

A single root trace per ``(config, product, run)`` makes every nested LLM call
(LangChain auto-traced, ``wrap_anthropic``-wrapped Anthropic, or ``@traceable``
Cohere) attach underneath it in the LangSmith UI — giving a turn-by-turn
reason -> act -> observe waterfall per run.

Everything here is a **cheap no-op when ``LANGSMITH_TRACING`` is unset** (or the
``langsmith`` package is unavailable), so the harness still runs fully offline.
"""

from __future__ import annotations

import contextlib
import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_TRUTHY = {"1", "true", "yes", "on"}


def tracing_enabled() -> bool:
    """True iff LangSmith tracing is switched on via env."""
    return os.environ.get("LANGSMITH_TRACING", "").strip().lower() in _TRUTHY


def project_name() -> Optional[str]:
    return os.environ.get("LANGSMITH_PROJECT")


@contextlib.contextmanager
def root_run(
    name: str,
    *,
    metadata: Optional[Dict[str, Any]] = None,
    tags: Optional[List[str]] = None,
):
    """Open a LangSmith root trace; yields the RunTree (or ``None`` if disabled).

    Usage::

        with root_run("cfg::prod::run0", metadata={...}, tags=[...]) as rt:
            result = await runner.run(inp)   # nested calls attach here
            if rt is not None:
                rt.add_metadata({"failure_type": ...})
    """
    if not tracing_enabled():
        yield None
        return
    try:
        from langsmith import trace as _ls_trace
    except Exception as e:  # langsmith missing / import error -> stay offline
        logger.debug("LangSmith unavailable, tracing skipped: %s", e)
        yield None
        return

    kwargs: Dict[str, Any] = {"name": name, "run_type": "chain"}
    if metadata:
        kwargs["metadata"] = metadata
    if tags:
        kwargs["tags"] = tags
    proj = project_name()
    if proj:
        kwargs["project_name"] = proj

    try:
        cm = _ls_trace(**kwargs)
    except Exception as e:
        # Construction failed — stay untraced, never break the run.
        logger.warning("LangSmith root_run init failed (continuing untraced): %s", e)
        yield None
        return
    # Caller-body exceptions propagate through the with (LangSmith records + re-raises).
    with cm as rt:
        yield rt
