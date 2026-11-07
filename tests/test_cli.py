from pathlib import Path

import pytest

from agentplayground import cli
from scoring.claude_cli import ClaudeResult
from scoring.lab import load_lab


@pytest.fixture
def ws(tmp_path, monkeypatch):
    """Point the CLI's workspace at a temp dir."""
    agents = tmp_path / ".claude" / "agents"
    monkeypatch.setattr(cli, "AGENTS_DIR", agents)
    return agents


def test_root_explains_flow_and_lists_labs(capsys, ws):
    assert cli.main([]) == 0
    out = capsys.readouterr().out
    for word in ("list", "show", "start", "check"):
        assert word in out
    assert "lab01" in out


def test_list_shows_labs_and_progress(capsys, ws):
    assert cli.main(["list"]) == 0
    out = capsys.readouterr().out
    assert "lab01" in out and "Contract" in out
    assert "[ ]" in out
    ws.mkdir(parents=True)
    (ws / "bug-hunter.md").write_text("x", encoding="utf-8")
    cli.main(["list"])
    assert "[x]" in capsys.readouterr().out


def test_show_prints_lab_readme(capsys, ws):
    assert cli.main(["show", "lab01"]) == 0
    out = capsys.readouterr().out
    readme = load_lab("lab01").root / "README.md"
    assert readme.read_text(encoding="utf-8").splitlines()[0] in out
    assert "agentplayground start lab01" in out


def test_unknown_lab_returns_1(capsys, ws):
    assert cli.main(["show", "nope"]) == 1
    assert "nope" in capsys.readouterr().out


def test_start_copies_starter_and_refuses_overwrite(capsys, ws):
    assert cli.main(["start", "lab01"]) == 0
    target = ws / "bug-hunter.md"
    starter = load_lab("lab01").root / "starter.md"
    assert target.read_text(encoding="utf-8") == starter.read_text(encoding="utf-8")
    target.write_text("mine", encoding="utf-8")
    assert cli.main(["start", "lab01"]) == 1
    assert target.read_text(encoding="utf-8") == "mine"
    assert "--force" in capsys.readouterr().out
    assert cli.main(["start", "lab01", "--force"]) == 0
    assert target.read_text(encoding="utf-8") != "mine"


def test_check_without_agent_says_start_first(capsys, ws):
    assert cli.main(["check", "lab01"]) == 1
    assert "agentplayground start lab01" in capsys.readouterr().out


def test_check_delegates_to_scorer(tmp_path, ws, monkeypatch):
    ws.mkdir(parents=True)
    agent = ws / "bug-hunter.md"
    agent.write_text("x", encoding="utf-8")
    seen = {}

    def fake_run_main(argv, runner=None):
        seen["argv"], seen["runner"] = argv, runner
        return 0

    monkeypatch.setattr(cli, "run_main", fake_run_main)
    sentinel = lambda *a: ClaudeResult("", [], 0.0, False, None, None, None)  # noqa: E731
    assert cli.main(["check", "lab01", "--quick"], runner=sentinel) == 0
    assert seen["argv"] == ["lab01", "--agent-file", str(agent), "--quick"]
    assert seen["runner"] is sentinel


def test_starter_earns_no_free_quality_checks():
    from scoring.structure import check_structure
    r = check_structure(load_lab("lab01").root / "starter.md", "bug-hunter")
    failed = {c.id for c in r.checks if not c.passed}
    assert not r.gate_passed
    assert {"read_only_tools", "output_schema", "json_only", "stopping_rule"} <= failed
