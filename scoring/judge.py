"""LLM judge: grades what coded checks cannot (cause, fix) and writes the critique."""
import dataclasses
import json
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from scoring.behavior import RunOutcome
from scoring.claude_cli import Runner
from scoring.jsonx import extract_json_object
from scoring.lab import Lab

JUDGE_AGENT_FILE = Path(__file__).parent / "judge" / "judge-agent.md"
JUDGE_TIMEOUT_S = 300
JUDGE_PROMPT = ("Grade the submission described in judge-input.json and agent-definition.md "
                "in the current directory. "
                "Follow your instructions exactly.")


@dataclass
class JudgeResult:
    cause_score: Optional[float]
    fix_score: Optional[float]
    critique: str
    suggestions: List[str]
    error: Optional[str]


def tool_calls(events: List[dict], limit: int = 40) -> List[dict]:
    calls = []  # type: List[dict]
    for ev in events:
        if not isinstance(ev, dict):
            continue
        msg = ev.get("message")
        content = msg.get("content") if isinstance(msg, dict) else None
        if not isinstance(content, list):
            continue
        for item in content:
            if isinstance(item, dict) and item.get("type") == "tool_use":
                raw = json.dumps(item.get("input"), ensure_ascii=False)
                calls.append({"tool": item.get("name"), "input": raw[:200]})
                if len(calls) >= limit:
                    return calls
    return calls


AGENT_DEFINITION_FILE = "agent-definition.md"
LINE_CAP = 500
TEXT_CAP = 2000


def _cap_lines(text: str) -> List[str]:
    """Split into short lines: Claude Code's Read truncates lines over 2000 chars."""
    return [ln[:LINE_CAP] for ln in text[:TEXT_CAP].splitlines()]


def _short_report(report: Optional[dict]) -> Optional[dict]:
    if report is None:
        return None
    return {k: (v[:LINE_CAP] if isinstance(v, str) else v) for k, v in report.items()}


def build_judge_input(lab: Lab, outcomes: List[RunOutcome]) -> dict:
    return {
        "lab": {"id": lab.id, "title": lab.title, "task_prompt": lab.task_prompt},
        "expected": dataclasses.asdict(lab.expected),
        "variant_expected": {v.name: dataclasses.asdict(v.expected) for v in lab.variants},
        "agent_definition_file": AGENT_DEFINITION_FILE,
        "runs": [{
            "run_id": o.run_id,
            "variant": o.variant,
            "report": _short_report(o.report.data),
            "strict_json": o.report.strict,
            "result_text_lines": _cap_lines(o.result_text),
            "code_checks": {"file_match": o.file_match, "line_match": o.line_match,
                            "edited_files": list(o.edited_files), "timed_out": o.timed_out,
                            "error": o.error},
            "tool_calls": tool_calls(o.events),
        } for o in outcomes],
    }


def _score(val: object) -> Optional[float]:
    if isinstance(val, bool) or not isinstance(val, (int, float)):
        return None
    return max(0, min(100, val))


def parse_verdict(text: str) -> JudgeResult:
    obj, _ = extract_json_object(text)
    if obj is None:
        return JudgeResult(None, None, "", [], "invalid judge verdict: no JSON object found")
    critique = obj.get("critique")
    critique = critique if isinstance(critique, str) else ""
    sugg = obj.get("suggestions")
    suggestions = [s for s in sugg if isinstance(s, str)][:3] if isinstance(sugg, list) else []
    cause, fix = _score(obj.get("cause_score")), _score(obj.get("fix_score"))
    if cause is None or fix is None:
        bad = "cause_score" if cause is None else "fix_score"
        return JudgeResult(None, None, critique, [], "invalid judge verdict: missing or invalid " + bad)
    return JudgeResult(cause, fix, critique, suggestions, None)


def run_judge(lab: Lab, agent_text: str, outcomes: List[RunOutcome], runner: Runner) -> JudgeResult:
    tmp = Path(tempfile.mkdtemp(prefix="judge-"))
    try:
        agents = tmp / ".claude" / "agents"
        agents.mkdir(parents=True)
        shutil.copyfile(str(JUDGE_AGENT_FILE), str(agents / "judge.md"))
        (tmp / AGENT_DEFINITION_FILE).write_text(agent_text, encoding="utf-8")
        (tmp / "judge-input.json").write_text(
            json.dumps(build_judge_input(lab, outcomes), indent=2, ensure_ascii=False),
            encoding="utf-8")
        try:
            res = runner(JUDGE_PROMPT, tmp, "judge", JUDGE_TIMEOUT_S)
        except Exception as exc:
            return JudgeResult(None, None, "", [], str(exc))
        if res.error or res.timed_out:
            return JudgeResult(None, None, "", [], res.error or "judge timed out")
        return parse_verdict(res.result_text)
    finally:
        shutil.rmtree(str(tmp), ignore_errors=True)
