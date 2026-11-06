"""Fake claude CLI for tests. Behavior driven by FAKE_CLAUDE_MODE."""
import json
import os
import sys
import time


def emit(obj):
    print(json.dumps(obj), flush=True)


def main():
    prompt = sys.stdin.read()
    mode = os.environ.get("FAKE_CLAUDE_MODE", "ok")
    emit({"type": "system", "subtype": "init", "tools": ["Read"]})
    if mode == "sleep":
        time.sleep(5)
    emit({"type": "assistant", "message": {"content": [
        {"type": "text", "text": "thinking"},
        {"type": "tool_use", "name": "Read", "input": {"file_path": "a.txt"}}]}})
    if mode == "noresult":
        return 0
    if mode == "error":
        sys.stderr.write("boom: something failed\n")
        return 1
    emit({"type": "result", "subtype": "success", "is_error": False,
          "result": "echo: " + prompt.strip(), "duration_ms": 10,
          "num_turns": 2, "total_cost_usd": 0.0144})
    return 0


if __name__ == "__main__":
    sys.exit(main())
