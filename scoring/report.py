"""Scorecard math, ASCII terminal report, and report.json + transcripts."""
import dataclasses
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from scoring.behavior import RunOutcome, code_behavior_score
from scoring.judge import JudgeResult
from scoring.lab import Lab
from scoring.robustness import RobustnessResult
from scoring.speed import speed_score
from scoring.structure import StructureResult


@dataclass
class Scorecard:
    structure: float
    behavior: Optional[float]
    speed: Optional[float]
    robustness: Optional[float]
    total: Optional[float]


def _round(v: Optional[float]) -> Optional[float]:
    return None if v is None else round(v, 1)


def compute_scorecard(lab: Lab, structure: StructureResult, outcomes: List[RunOutcome],
                      robustness: Optional[RobustnessResult],
                      judge: Optional[JudgeResult]) -> Scorecard:
    behavior = None  # type: Optional[float]
    speed = None  # type: Optional[float]
    rob = None  # type: Optional[float]
    if outcomes:
        base = [o for o in outcomes if o.variant == "base"]
        first = base[0] if base else outcomes[0]
        behavior = code_behavior_score(first)
        if judge is not None and judge.cause_score is not None and judge.fix_score is not None:
            behavior = 0.5 * behavior + 0.5 * (judge.cause_score + judge.fix_score) / 2.0
        speeds = [speed_score(o.duration_s, lab.time_budget_s, o.timed_out) for o in outcomes]
        speed = sum(speeds) / len(speeds)
        rob = robustness.score if robustness is not None else None
    dims = {"structure": structure.score, "behavior": behavior, "speed": speed,
            "robustness": rob}
    num = den = 0.0
    for name, val in dims.items():
        if val is None:
            continue
        w = lab.weights.get(name, 0.0)
        num += w * val
        den += w
    total = round(num / den, 1) if den > 0 and outcomes else None
    return Scorecard(structure=_round(structure.score), behavior=_round(behavior),
                     speed=_round(speed), robustness=_round(rob), total=total)


def _ascii(text: object) -> str:
    return str(text).encode("ascii", "replace").decode("ascii")


def _fmt(v: Optional[float]) -> str:
    return "-" if v is None else "%.1f" % v


def _tok(n: Optional[int]) -> str:
    if n is None:
        return "-"
    return str(n) if n < 1000 else "%.1fk" % (n / 1000.0)


def _sum(vals) -> Optional[float]:
    known = [v for v in vals if v is not None]
    return sum(known) if known else None


def _usage(items) -> dict:
    """Token/cost totals over outcomes or judge results; unknown values are skipped."""
    items = list(items)
    return {"input": _sum(i.input_tokens for i in items),
            "output": _sum(i.output_tokens for i in items),
            "cost_usd": _sum(i.cost_usd for i in items)}


def _usage_str(u: dict) -> str:
    cost = "-" if u["cost_usd"] is None else "$%.2f" % u["cost_usd"]
    return "%s in / %s out (%s)" % (_tok(u["input"]), _tok(u["output"]), cost)


def token_summary(outcomes: List[RunOutcome], judge: Optional[JudgeResult]) -> dict:
    agent = _usage(outcomes)
    judge_u = _usage([judge] if judge is not None else [])
    agent["cost_usd"] = None if agent["cost_usd"] is None else round(agent["cost_usd"], 4)
    judge_u["cost_usd"] = None if judge_u["cost_usd"] is None else round(judge_u["cost_usd"], 4)
    total = _sum([agent["cost_usd"], judge_u["cost_usd"]])
    return {"agent": agent, "judge": judge_u,
            "total_cost_usd": None if total is None else round(total, 4)}


def _reason(o: RunOutcome) -> str:
    if o.passed:
        return ""
    if o.error:
        return o.error
    if o.timed_out:
        return "timed out"
    if o.edited_files:
        return "edited files: " + ", ".join(o.edited_files)
    if o.report.error:
        return o.report.error
    return "wrong location"


def render(lab: Lab, scorecard: Scorecard, structure: StructureResult,
           outcomes: List[RunOutcome], robustness: Optional[RobustnessResult],
           judge: Optional[JudgeResult], no_judge: bool = False) -> str:
    out = []  # type: List[str]
    title = "%s - %s" % (lab.id, lab.title)
    bar = "=" * max(40, len(title))
    out += [bar, _ascii(title), bar, ""]
    out.append("%-12s %8s %8s" % ("dimension", "score", "weight"))
    for name in ("structure", "behavior", "speed", "robustness"):
        out.append("%-12s %8s %8s" % (name, _fmt(getattr(scorecard, name)),
                                      "%g" % lab.weights.get(name, 0.0)))
    out.append("%-12s %8s" % ("TOTAL", _fmt(scorecard.total)))
    out.append("")
    failed = [c for c in structure.checks if not c.passed]
    if failed:
        out.append("Structure checks failed:")
        for c in failed:
            out.append(_ascii("  - %s%s: %s" % (c.id, " (critical)" if c.critical else "", c.hint)))
        out.append("")
    if outcomes:
        out.append("Runs:")
        for o in outcomes:
            d = o.report.data
            loc = "%s:%s" % (d["file"], d["line"]) if d else "-"
            line = "%s %-16s %-22s %6.1fs  %-22s %s" % (
                "PASS" if o.passed else "FAIL", o.run_id, loc, o.duration_s,
                "%s in / %s out" % (_tok(o.input_tokens), _tok(o.output_tokens)), _reason(o))
            out.append(_ascii("  " + line.rstrip()))
        out.append("")
        t = token_summary(outcomes, judge)
        total = "-" if t["total_cost_usd"] is None else "$%.2f" % t["total_cost_usd"]
        out.append("Tokens: agent %s | judge %s | total %s"
                   % (_usage_str(t["agent"]), _usage_str(t["judge"]), total))
        out.append("")
    if robustness is not None and not robustness.skipped:
        out.append("Robustness: %d/%d runs passed; base runs %s" % (
            robustness.passed_runs, robustness.total_runs,
            "consistent" if robustness.consistent else "not consistent"))
        out.append("")
    if outcomes and judge is None:
        out.append("judge: skipped (--no-judge)" if no_judge
                   else "judge: not run (behavior = code checks only)")
        if no_judge:
            out.append("(behavior = code checks only)")
    elif judge is not None:
        if judge.error or judge.cause_score is None or judge.fix_score is None:
            out.append(_ascii("judge unavailable: %s (behavior = code checks only)"
                              % (judge.error or "no scores")))
        else:
            out.append("Judge: cause %s, fix %s" % (_fmt(judge.cause_score), _fmt(judge.fix_score)))
            out.append(_ascii("  " + judge.critique))
            for s in judge.suggestions:
                out.append(_ascii("  * " + s))
    return "\n".join(out) + "\n"


def _jsonable(obj):
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {f.name: _jsonable(getattr(obj, f.name)) for f in dataclasses.fields(obj)}
    if isinstance(obj, dict):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    if isinstance(obj, Path):
        return obj.as_posix()
    return obj


def write_report(out_dir: Path, lab: Lab, scorecard: Scorecard, structure: StructureResult,
                 outcomes: List[RunOutcome], robustness: Optional[RobustnessResult],
                 judge: Optional[JudgeResult], agent_file: Optional[Path] = None) -> Path:
    out_dir = Path(out_dir)
    tdir = out_dir / "transcripts"
    tdir.mkdir(parents=True, exist_ok=True)
    runs = []
    for o in outcomes:
        d = _jsonable(o)
        d.pop("events", None)
        runs.append(d)
        with open(str(tdir / (o.run_id + ".jsonl")), "w", encoding="utf-8") as fh:
            for ev in o.events:
                fh.write(json.dumps(ev, ensure_ascii=False) + "\n")
    data = {
        "lab": lab.id,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "agent_file": _jsonable(agent_file) if agent_file is not None else None,
        "scorecard": _jsonable(scorecard),
        "structure": _jsonable(structure),
        "runs": runs,
        "robustness": _jsonable(robustness),
        "judge": _jsonable(judge),
        "tokens": token_summary(outcomes, judge),
    }
    path = out_dir / "report.json"
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return path
