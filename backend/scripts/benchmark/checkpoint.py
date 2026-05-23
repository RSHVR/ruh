"""Checkpoint / resume for the eval run.

``output/.checkpoint.json`` is updated after every completed run via an
atomic temp-file rename. ``--resume`` skips tuples that are already there.
A ``config_hash`` (sha256 over prompts + tool schemas + dataset) invalidates
the checkpoint if any of those change, preventing silent mixing of
incompatible runs.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import signal
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


def compute_config_hash(*files: Path) -> str:
    h = hashlib.sha256()
    for f in files:
        try:
            with open(f, "rb") as fh:
                h.update(fh.read())
        except FileNotFoundError:
            h.update(b"<missing>")
    return h.hexdigest()


@dataclass
class Checkpoint:
    path: Path
    config_hash: str
    completed: Set[Tuple[str, str, int]] = field(default_factory=set)
    spent_usd: float = 0.0

    def is_completed(self, config: str, product_id: str, run_idx: int) -> bool:
        return (config, product_id, run_idx) in self.completed

    def mark_completed(
        self, config: str, product_id: str, run_idx: int, cost_usd: float
    ) -> None:
        self.completed.add((config, product_id, run_idx))
        self.spent_usd += float(cost_usd)
        self.flush()

    def flush(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "config_hash": self.config_hash,
            "completed": [list(t) for t in sorted(self.completed)],
            "spent_usd": round(self.spent_usd, 6),
        }
        # Atomic temp-file rename so we never leave a half-written checkpoint.
        fd, tmp = tempfile.mkstemp(prefix=".ckpt.", dir=str(self.path.parent))
        try:
            with os.fdopen(fd, "w") as fh:
                json.dump(payload, fh, indent=2)
            os.replace(tmp, self.path)
        finally:
            if os.path.exists(tmp):
                try:
                    os.unlink(tmp)
                except OSError:
                    pass

    @classmethod
    def load_or_create(
        cls, path: Path, config_hash: str, resume: bool
    ) -> "Checkpoint":
        if path.exists() and resume:
            try:
                data = json.loads(path.read_text())
            except json.JSONDecodeError as e:
                logger.warning("Checkpoint corrupt (%s); starting fresh", e)
                return cls(path=path, config_hash=config_hash)
            saved_hash = data.get("config_hash")
            if saved_hash != config_hash:
                raise RuntimeError(
                    f"Checkpoint at {path} has config_hash={saved_hash} but current "
                    f"config_hash={config_hash}. Refusing to resume — delete the "
                    "checkpoint or revert the changed source files."
                )
            completed = {tuple(t) for t in data.get("completed", [])}
            return cls(
                path=path,
                config_hash=config_hash,
                completed=completed,
                spent_usd=float(data.get("spent_usd", 0.0)),
            )
        return cls(path=path, config_hash=config_hash)


def install_signal_flush(checkpoint: Checkpoint) -> None:
    """Best-effort SIGINT/SIGTERM handler that flushes the checkpoint.

    The default handler is restored so a second Ctrl-C kills the process.
    """

    def _handler(signum, _frame):
        logger.warning("Signal %s received — flushing checkpoint", signum)
        try:
            checkpoint.flush()
        finally:
            signal.signal(signum, signal.SIG_DFL)
            os.kill(os.getpid(), signum)

    signal.signal(signal.SIGINT, _handler)
    signal.signal(signal.SIGTERM, _handler)
