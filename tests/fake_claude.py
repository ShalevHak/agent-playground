"""Fake claude CLI for tests. Behavior driven by FAKE_CLAUDE_MODE."""
import json
import os
import subprocess
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
    if mode == "sleep_child":
        subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
        time.sleep(30)
    emit({"type": "assistant", "message": {"content": [
        {"type": "text", "text": "thinking"},
        {"type": "tool_use", "name": "Read", "input": {"file_path": "a.txt"}}]}})
    if mode == "noresult":
        return 0
    if mode == "error":
        sys.stderr.write("boom: something failed\n")
        return 1
    if mode in ("is_error", "exit_with_result"):
        emit({"type": "result", "subtype": "error", "is_error": True,
              "result": "Credit balance is too low"})
        return 1 if mode == "exit_with_result" else 0
    emit({"type": "result", "subtype": "success", "is_error": False,
          "result": "echo: " + prompt.strip(), "duration_ms": 10,
          "num_turns": 2, "total_cost_usd": 0.0144,
          "usage": {"input_tokens": 100, "cache_creation_input_tokens": 20,
                    "cache_read_input_tokens": 300, "output_tokens": 40}})
    return 0


if __name__ == "__main__":
    sys.exit(main())
