import json
from pathlib import Path

from scoring.claude_cli import ClaudeResult
from scoring.run import main

AGENT = """---
name: bug-hunter
description: Finds the root cause of a bug. Use when asked to locate a bug.
tools: Read, Grep, Glob
---
Investigate the repository read-only. Reply with JSON only, with keys file, line,
cause and fix. Stop as soon as you have found the cause.
"""


def fake_runner(prompt, cwd, agent, timeout_s):
    if agent == "judge":
        text = json.dumps({"cause_score": 100, "fix_score": 100, "critique": "good",
                           "suggestions": []})
    else:
        found = None
        for name in ("pricing.py", "rates.py"):
            p = Path(cwd) / "shop" / name
            if p.is_file():
                for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
                    if "if qty > BULK_THRESHOLD" in line:
                        found = ("shop/" + name, i)
                        break
            if found:
                break
        text = json.dumps({"file": found[0], "line": found[1], "cause": "off by one",
                           "fix": "use >="})
    return ClaudeResult(text, [{"type": "result"}], 1.0, False, None, 1, 0.0)


def test_main_end_to_end(tmp_path, capsys):
    agent = tmp_path / "bug-hunter.md"
    agent.write_text(AGENT, encoding="utf-8")
    runs = tmp_path / "runs"
    rc = main(["lab01", "--agent-file", str(agent), "--runs-dir", str(runs)], runner=fake_runner)
    assert rc == 0
    dirs = list(runs.iterdir())
    assert len(dirs) == 1
    data = json.loads((dirs[0] / "report.json").read_text(encoding="utf-8"))
    assert data["scorecard"]["total"] >= 90
    assert (dirs[0] / "transcripts" / "base-1.jsonl").is_file()
    assert "running base-1..." in capsys.readouterr().out


def test_main_quick_no_judge(tmp_path):
    agent = tmp_path / "bug-hunter.md"
    agent.write_text(AGENT, encoding="utf-8")
    rc = main(["lab01", "--quick", "--no-judge", "--agent-file", str(agent),
               "--runs-dir", str(tmp_path / "runs")], runner=fake_runner)
    assert rc == 0
    d = next((tmp_path / "runs").iterdir())
    data = json.loads((d / "report.json").read_text(encoding="utf-8"))
    assert len(data["runs"]) == 1 and data["judge"] is None


def test_gate_failure(tmp_path, capsys):
    rc = main(["lab01", "--agent-file", str(tmp_path / "missing.md"),
               "--runs-dir", str(tmp_path / "runs")], runner=fake_runner)
    assert rc == 2
    assert "fix the structure errors above before running" in capsys.readouterr().out
    assert not (tmp_path / "runs").exists()


def test_unknown_lab(capsys):
    assert main(["nope"], runner=fake_runner) == 1
    assert "not found" in capsys.readouterr().out
