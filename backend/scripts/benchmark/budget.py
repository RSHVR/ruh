"""Budget guardrail — pre-flight estimate + per-run accumulation.

The runner consults ``BudgetTracker.would_exceed(extra_cost)`` before invoking
a config. After each completed run it calls ``BudgetTracker.add(cost)`` from
the ``AnalysisTokenSummary.total_cost``. ``Pre-flight estimate * 1.4 > cap``
without ``--force`` refuses to start.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


class BudgetExceeded(Exception):
    """Raised when an add() would push the spend past the cap."""


@dataclass
class BudgetTracker:
    max_cost_usd: float
    warn_at: float = 0.75   # fraction of cap at which we log a warning
    spent_usd: float = 0.0
    _warned: bool = False

    def remaining(self) -> float:
        return max(0.0, self.max_cost_usd - self.spent_usd)

    def would_exceed(self, extra_cost_usd: float) -> bool:
        return (self.spent_usd + extra_cost_usd) > self.max_cost_usd

    def add(self, cost_usd: float) -> None:
        if cost_usd < 0:
            raise ValueError(f"add() got negative cost {cost_usd}")
        if self.would_exceed(cost_usd):
            new_total = self.spent_usd + cost_usd
            raise BudgetExceeded(
                f"would push spend to ${new_total:.2f} > cap ${self.max_cost_usd:.2f}"
            )
        self.spent_usd += cost_usd
        if not self._warned and self.spent_usd >= self.warn_at * self.max_cost_usd:
            logger.warning(
                "Budget at %.0f%% of cap ($%.2f / $%.2f)",
                100 * self.spent_usd / self.max_cost_usd,
                self.spent_usd,
                self.max_cost_usd,
            )
            self._warned = True

    @staticmethod
    def preflight(
        estimated_total_cost: float,
        max_cost_usd: float,
        margin: float = 1.4,
        force: bool = False,
    ) -> None:
        """Raise BudgetExceeded if estimate * margin > cap (unless force=True)."""
        projected = estimated_total_cost * margin
        if not force and projected > max_cost_usd:
            raise BudgetExceeded(
                f"pre-flight: estimate ${estimated_total_cost:.2f} * {margin}x = "
                f"${projected:.2f} exceeds cap ${max_cost_usd:.2f}. Pass --force to override."
            )
        logger.info(
            "Pre-flight check: estimate $%.2f, projected $%.2f, cap $%.2f, OK",
            estimated_total_cost,
            projected,
            max_cost_usd,
        )
