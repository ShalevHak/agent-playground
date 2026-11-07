"""Run `claude -p` headless and parse its stream-json output."""
import json
import os
import shutil
import signal
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
    input_tokens: Optional[int] = None   # prompt tokens incl. cache reads/writes
    output_tokens: Optional[int] = None


def usage_tokens(res: Optional[dict]) -> Tuple[Optional[int], Optional[int]]:
    """(input, output) tokens from a result event's `usage`, or (None, None)."""
    usage = res.get("usage") if res else None
    if not isinstance(usage, dict):
        return None, None
    keys = ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")
    inp = sum(int(usage.get(k) or 0) for k in keys)
    return inp, int(usage.get("output_tokens") or 0)


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


def _kill_tree(proc: "subprocess.Popen") -> None:
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        else:
            os.killpg(proc.pid, signal.SIGKILL)
    except Exception:
        pass
    try:
        proc.kill()
    except Exception:
        pass


def run_claude(prompt: str, cwd: Path, agent: str, timeout_s: float,
               claude_cmd: Optional[List[str]] = None) -> ClaudeResult:
    if claude_cmd is None:
        claude_cmd = find_claude()
    cmd = list(claude_cmd) + ["-p", "--agent", agent] + CLAUDE_FLAGS
    start = time.time()
    proc = subprocess.Popen(cmd, cwd=str(cwd), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, encoding="utf-8", errors="replace",
                            start_new_session=(os.name != "nt"))
    timed_out = False
    try:
        stdout, stderr = proc.communicate(prompt, timeout=timeout_s)
    except subprocess.TimeoutExpired:
        timed_out = True
        _kill_tree(proc)
        try:
            stdout, stderr = proc.communicate(timeout=5)
        except subprocess.TimeoutExpired as exc:
            stdout, stderr = exc.stdout, exc.stderr
            for pipe in (proc.stdout, proc.stderr, proc.stdin):
                try:
                    if pipe:
                        pipe.close()
                except Exception:
                    pass
            if isinstance(stdout, bytes):
                stdout = stdout.decode("utf-8", errors="replace")
            if isinstance(stderr, bytes):
                stderr = stderr.decode("utf-8", errors="replace")
    except BaseException:
        _kill_tree(proc)
        raise
    duration = time.time() - start
    events, res = parse_stream((stdout or "").splitlines())

    error = None  # type: Optional[str]
    if timed_out:
        error = "timed out after %gs" % timeout_s
    elif proc.returncode != 0:
        error = "exit code %s: %s" % (proc.returncode, (stderr or "")[-500:])
        if res is not None and res.get("result"):
            error += " | result: %s" % str(res.get("result"))[:300]
    elif res is None:
        error = "no result event in claude output"
    elif res.get("is_error"):
        error = "claude reported an error: %s" % str(res.get("result", ""))[:300]

    text = ""
    if res is not None and isinstance(res.get("result"), str):
        text = res["result"]
    inp, outp = usage_tokens(res)
    return ClaudeResult(result_text=text, events=events, duration_s=duration,
                        timed_out=timed_out, error=error,
                        num_turns=res.get("num_turns") if res else None,
                        cost_usd=res.get("total_cost_usd") if res else None,
                        input_tokens=inp, output_tokens=outp)
