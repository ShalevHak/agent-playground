"""Robustness score: share of runs (base + variants) that passed."""
from dataclasses import dataclass
from typing import List, Optional

from scoring.behavior import RunOutcome


@dataclass
class RobustnessResult:
    score: Optional[float]
    consistent: Optional[bool]
    passed_runs: int
    total_runs: int
    skipped: bool


def score_robustness(outcomes: List[RunOutcome], quick: bool) -> RobustnessResult:
    total = len(outcomes)
    passed = sum(1 for o in outcomes if o.passed)
    if quick:
        return RobustnessResult(None, None, passed, total, True)
    base = [o for o in outcomes if o.variant == "base"]
    consistent = bool(base) and all(o.passed for o in base) and len(
        set((o.report.data["file"], o.report.data["line"]) for o in base)) == 1
    score = 100.0 * passed / total if total else 0.0
    return RobustnessResult(score, consistent, passed, total, False)
