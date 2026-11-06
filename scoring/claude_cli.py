"""Run `claude -p` headless and parse its stream-json output."""
import json
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, List, Optional, Tuple

CLAUDE_FLAGS = ["--output-format", "stream-json", "--verbose", "--setting-sources", "project",
                "--strict-mcp-config", "--no-session-persistence"]


@dataclass
class ClaudeResult:
    result_text: str
    events: List[dict]
    duration_s: float
    timed_out: bool
    error: Optional[str]
    num_turns: Optional[int]
    cost_usd: Optional[float]


Runner = Callable[[str, Path, str, float], ClaudeResult]


class ClaudeNotAvailable(Exception):
    pass


def find_claude() -> List[str]:
    path = shutil.which("claude")
    if not path:
        raise ClaudeNotAvailable(
            "claude CLI not found on PATH. Install Claude Code and run `claude` once to log in.")
    return [path]


def parse_stream(lines: Iterable[str]) -> Tuple[List[dict], Optional[dict]]:
    events = []  # type: List[dict]
    result = None  # type: Optional[dict]
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        if not isinstance(obj, dict):
            continue
        events.append(obj)
        if obj.get("type") == "result":
            result = obj
    return events, result


def run_claude(prompt: str, cwd: Path, agent: str, timeout_s: float,
               claude_cmd: Optional[List[str]] = None) -> ClaudeResult:
    if claude_cmd is None:
        claude_cmd = find_claude()
    cmd = list(claude_cmd) + ["-p", "--agent", agent] + CLAUDE_FLAGS
    start = time.time()
    proc = subprocess.Popen(cmd, cwd=str(cwd), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, encoding="utf-8", errors="replace")
    timed_out = False
    try:
        stdout, stderr = proc.communicate(prompt, timeout=timeout_s)
    except subprocess.TimeoutExpired:
        timed_out = True
        proc.kill()
        stdout, stderr = proc.communicate()
    duration = time.time() - start
    events, res = parse_stream((stdout or "").splitlines())

    error = None  # type: Optional[str]
    if timed_out:
        error = "timed out after %gs" % timeout_s
    elif proc.returncode != 0:
        error = "exit code %s: %s" % (proc.returncode, (stderr or "")[-500:])
    elif res is None:
        error = "no result event in claude output"
    elif res.get("is_error"):
        error = "claude reported an error: %s" % str(res.get("result", ""))[-500:]

    text = ""
    if res is not None and isinstance(res.get("result"), str):
        text = res["result"]
    return ClaudeResult(result_text=text, events=events, duration_s=duration,
                        timed_out=timed_out, error=error,
                        num_turns=res.get("num_turns") if res else None,
                        cost_usd=res.get("total_cost_usd") if res else None)
