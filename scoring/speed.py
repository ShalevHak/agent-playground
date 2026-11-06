"""Speed score: full marks within budget, linear decay to 0 at 3x budget."""


def speed_score(duration_s: float, budget_s: float, timed_out: bool = False) -> float:
    if timed_out or duration_s >= 3 * budget_s:
        return 0.0
    if duration_s <= budget_s:
        return 100.0
    return 100.0 * (3 * budget_s - duration_s) / (2 * budget_s)
