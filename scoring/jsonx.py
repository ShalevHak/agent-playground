"""Extract a JSON object from model output."""
import json
import re
from typing import Optional, Tuple

_FENCE = re.compile(r"```([A-Za-z0-9_+-]*)[ \t]*\r?\n(.*?)```", re.DOTALL)


def _parse_dict(s: str) -> Optional[dict]:
    try:
        obj = json.loads(s)
    except ValueError:
        return None
    return obj if isinstance(obj, dict) else None


def _balanced_end(text: str, start: int) -> int:
    """Index just past the brace-balanced object starting at start, or -1."""
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return i + 1
    return -1


def extract_json_object(text: str) -> Tuple[Optional[dict], bool]:
    """Return (obj, strict). strict is True when the whole text is the object."""
    if not text or not text.strip():
        return None, False
    obj = _parse_dict(text.strip())
    if obj is not None:
        return obj, True
    for m in _FENCE.finditer(text):
        if m.group(1).lower() not in ("", "json"):
            continue
        obj = _parse_dict(m.group(2).strip())
        if obj is not None:
            return obj, False
    pos = text.find("{")
    while pos != -1:
        end = _balanced_end(text, pos)
        if end != -1:
            obj = _parse_dict(text[pos:end])
            if obj is not None:
                return obj, False
        pos = text.find("{", pos + 1)
    return None, False
