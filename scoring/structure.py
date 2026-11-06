"""Static structure checks on a learner-written agent .md file."""
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

import yaml

READ_ONLY_TOOLS = {"Read", "Grep", "Glob"}

_EARLIER = "fix the earlier error first"
_STOP = re.compile(r"\b(stop|stopping|done when|finish(ed)? when|as soon as)\b", re.I)
_SCHEMA_WORDS = ("file", "line", "cause", "fix")


@dataclass
class Check:
    id: str
    passed: bool
    critical: bool
    hint: str


@dataclass
class StructureResult:
    checks: List[Check]
    score: float
    gate_passed: bool


def _split_frontmatter(text: str) -> Optional[Tuple[object, str]]:
    """Return (parsed yaml, body), or None if there is no frontmatter block."""
    lines = text.lstrip("\ufeff").splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            block = "".join(lines[1:i])
            body = "".join(lines[i + 1:])
            try:
                return yaml.safe_load(block), body
            except Exception:
                return None
    return None


def _tool_list(value) -> List[str]:
    if isinstance(value, str):
        items = value.split(",")
    elif isinstance(value, list):
        items = value
    else:
        return []
    return [str(t).strip() for t in items if str(t).strip()]


def check_structure(agent_file: Path, agent_name: str) -> StructureResult:
    agent_file = Path(agent_file)
    checks: List[Check] = []

    def add(cid, passed, critical, hint):
        checks.append(Check(cid, bool(passed), critical, "" if passed else hint))

    def skip_rest(ids):
        for cid, critical in ids:
            add(cid, False, critical, _EARLIER)

    rest_after_exists = [
        ("frontmatter", True), ("name_matches", True), ("description", False),
        ("tools_declared", False), ("read_only_tools", True),
        ("output_schema", False), ("json_only", False), ("stopping_rule", False)]

    text = None
    if agent_file.is_file():
        try:
            text = agent_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            text = None
    add("exists", text is not None, True,
        "create the agent file at " + agent_file.as_posix())
    if text is None:
        skip_rest(rest_after_exists)
        return _result(checks)

    parsed = _split_frontmatter(text)
    fm_ok = parsed is not None and isinstance(parsed[0], dict)
    add("frontmatter", fm_ok, True,
        "start the file with a --- line, a valid YAML block of key: value pairs, then a closing ---")
    if not fm_ok:
        skip_rest(rest_after_exists[1:])
        return _result(checks)
    fm, body = parsed

    name = fm.get("name")
    add("name_matches", isinstance(name, str) and name == agent_name, True,
        "set `name: %s` in the frontmatter (it must match the agent file name)" % agent_name)

    desc = fm.get("description")
    add("description", isinstance(desc, str) and desc.strip() != "", False,
        "add a non-empty `description:` saying what the agent does and when to use it")

    tools = _tool_list(fm.get("tools"))
    add("tools_declared", bool(tools), False,
        "add a `tools:` line listing the tools the agent may use, e.g. `tools: Read, Grep, Glob`")

    bad = [t for t in tools if t not in READ_ONLY_TOOLS]
    if not tools:
        ro_hint = "declare `tools:` with only Read, Grep and Glob"
    else:
        ro_hint = "remove non-read-only tools (%s); allow only Read, Grep, Glob" % ", ".join(bad)
    add("read_only_tools", bool(tools) and not bad, True, ro_hint)

    missing = [w for w in _SCHEMA_WORDS
               if not re.search(r"\b%s\b" % w, body, re.I)]
    add("output_schema", not missing, False,
        "define the output fields in the body; missing: %s" % ", ".join(missing))
    add("json_only", re.search(r"JSON", body, re.I) is not None, False,
        "tell the agent to reply with JSON only")
    add("stopping_rule", _STOP.search(body) is not None, False,
        "add a stopping rule, e.g. 'Stop as soon as you have found the cause'")
    return _result(checks)


def _result(checks: List[Check]) -> StructureResult:
    passed = sum(1 for c in checks if c.passed)
    return StructureResult(
        checks=checks,
        score=100.0 * passed / len(checks),
        gate_passed=all(c.passed for c in checks if c.critical),
    )
