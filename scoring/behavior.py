"""Run the agent on the base task and variants; evaluate each run with coded checks."""
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional

from scoring.claude_cli import ClaudeResult, Runner
from scoring.jsonx import extract_json_object
from scoring.lab import Expected, Lab
from scoring.workspace import build_workspace, changed_files, snapshot

REPORT_KEYS = ("file", "line", "cause", "fix")


@dataclass
class ParsedReport:
    data: Optional[dict]
    strict: bool
    error: Optional[str]


@dataclass
class RunOutcome:
    run_id: str
    variant: str
    report: ParsedReport
    file_match: bool
    line_match: bool
    edited_files: List[str]
    duration_s: float
    timed_out: bool
    error: Optional[str]
    result_text: str
    events: List[dict]
    passed: bool


def parse_report(text: str) -> ParsedReport:
    obj, _strict = extract_json_object(text)
    if obj is None:
        return ParsedReport(None, False, "no JSON object found")
    missing = [k for k in REPORT_KEYS if k not in obj]
    if missing:
        return ParsedReport(None, False, "missing keys: " + ", ".join(missing))
    for key in REPORT_KEYS:
        val = obj[key]
        ok = (isinstance(val, int) and not isinstance(val, bool)) if key == "line" \
            else isinstance(val, str)
        if not ok:
            return ParsedReport(None, False, "wrong type for key: " + key)
    return ParsedReport(obj, _strict, None)


def normalize_path(p: str) -> str:
    p = p.replace("\\", "/")
    while p.startswith("./"):
        p = p[2:]
    return p.lstrip("/")


def file_matches(reported: str, expected: str) -> bool:
    r, e = normalize_path(reported), normalize_path(expected)
    return r == e or r.endswith("/" + e)


def evaluate_run(run_id: str, variant: str, expected: Expected, line_tolerance: int,
                 result: ClaudeResult, edited_files: List[str]) -> RunOutcome:
    report = parse_report(result.result_text)
    data = report.data
    file_ok = bool(data) and file_matches(data["file"], expected.file)
    line_ok = bool(data) and abs(data["line"] - expected.line) <= line_tolerance
    passed = (data is not None and file_ok and line_ok
              and not result.timed_out and result.error is None)
    return RunOutcome(run_id=run_id, variant=variant, report=report, file_match=file_ok,
                      line_match=line_ok, edited_files=list(edited_files),
                      duration_s=result.duration_s, timed_out=result.timed_out,
                      error=result.error, result_text=result.result_text,
                      events=result.events, passed=passed)


def code_behavior_score(outcome: RunOutcome) -> float:
    checks = [outcome.report.data is not None, outcome.file_match, outcome.line_match]
    return 100.0 * sum(1 for c in checks if c) / len(checks)


def execute_runs(lab: Lab, agent_file: Path, runner: Runner, quick: bool = False,
                 on_progress: Optional[Callable[[str], None]] = None) -> List[RunOutcome]:
    plan = [("base-%d" % i, "base", None, lab.expected)
            for i in range(1, (1 if quick else lab.consistency_runs) + 1)]
    if not quick:
        plan += [("variant-" + v.name, v.name, v, v.expected) for v in lab.variants]
    outcomes = []  # type: List[RunOutcome]
    for run_id, name, variant, expected in plan:
        if on_progress:
            on_progress(run_id)
        ws = build_workspace(lab, variant, agent_file)
        try:
            before = snapshot(ws)
            try:
                result = runner(lab.task_prompt, ws, lab.agent_name, lab.timeout_s)
            except Exception as exc:
                result = ClaudeResult(result_text="", events=[], duration_s=0.0,
                                      timed_out=False, error=str(exc), num_turns=None,
                                      cost_usd=None)
            edited = changed_files(before, snapshot(ws))
            outcomes.append(evaluate_run(run_id, name, expected, lab.line_tolerance,
                                         result, edited))
        finally:
            shutil.rmtree(str(ws), ignore_errors=True)
    return outcomes
