import sys
from pathlib import Path

import pytest

from scoring import claude_cli
from scoring.claude_cli import (ClaudeNotAvailable, find_claude, parse_stream,
                                run_claude)

FAKE = [sys.executable, str(Path(__file__).parent / "fake_claude.py")]


def test_parse_stream_skips_junk_and_finds_result():
    lines = ['', 'not json', '{"type":"system"}', '{"type":"result","result":"a"}',
             '{"type":"result","result":"b"}', '[1]']
    events, result = parse_stream(lines)
    assert len(events) == 3
    assert result["result"] == "b"


def test_parse_stream_no_result():
    events, result = parse_stream(['{"type":"system"}'])
    assert len(events) == 1 and result is None


def test_find_claude_missing(monkeypatch):
    monkeypatch.setattr(claude_cli.shutil, "which", lambda n: None)
    with pytest.raises(ClaudeNotAvailable) as e:
        find_claude()
    assert "claude CLI not found on PATH" in str(e.value)


def test_find_claude_found(monkeypatch):
    monkeypatch.setattr(claude_cli.shutil, "which", lambda n: "/x/claude")
    assert find_claude() == ["/x/claude"]


def test_run_ok(monkeypatch, tmp_path):
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "ok")
    r = run_claude("hello", tmp_path, "myagent", 30, claude_cmd=FAKE)
    assert r.error is None and not r.timed_out
    assert r.result_text == "echo: hello"
    assert r.num_turns == 2 and r.cost_usd == 0.0144
    assert len(r.events) == 3 and r.duration_s >= 0


def test_run_error(monkeypatch, tmp_path):
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "error")
    r = run_claude("hi", tmp_path, "a", 30, claude_cmd=FAKE)
    assert r.error and "boom" in r.error
    assert r.result_text == ""


def test_run_noresult(monkeypatch, tmp_path):
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "noresult")
    r = run_claude("hi", tmp_path, "a", 30, claude_cmd=FAKE)
    assert r.error and "result" in r.error
    assert len(r.events) == 2


def test_run_timeout(monkeypatch, tmp_path):
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "sleep")
    r = run_claude("hi", tmp_path, "a", 1, claude_cmd=FAKE)
    assert r.timed_out
    assert r.error == "timed out after 1s"
    assert r.duration_s < 4
    assert len(r.events) >= 1


def test_run_timeout_with_grandchild_holding_pipe(monkeypatch, tmp_path):
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "sleep_child")
    r = run_claude("hi", tmp_path, "a", 1, claude_cmd=FAKE)
    assert r.timed_out
    assert r.duration_s < 15
    assert len(r.events) >= 1


def test_run_is_error_includes_result_text(monkeypatch, tmp_path):
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "is_error")
    r = run_claude("hi", tmp_path, "a", 30, claude_cmd=FAKE)
    assert r.error and "Credit balance is too low" in r.error


def test_run_nonzero_exit_includes_result_text(monkeypatch, tmp_path):
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "exit_with_result")
    r = run_claude("hi", tmp_path, "a", 30, claude_cmd=FAKE)
    assert r.error and r.error.startswith("exit code 1")
    assert "Credit balance is too low" in r.error


def test_keyboard_interrupt_kills_process_tree(monkeypatch, tmp_path):
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "sleep")
    killed = []
    real_kill = claude_cli._kill_tree

    def spy(proc):
        killed.append(proc.pid)
        real_kill(proc)

    def boom(self, *a, **kw):
        raise KeyboardInterrupt()

    monkeypatch.setattr(claude_cli, "_kill_tree", spy)
    monkeypatch.setattr(claude_cli.subprocess.Popen, "communicate", boom)
    with pytest.raises(KeyboardInterrupt):
        run_claude("hi", tmp_path, "a", 30, claude_cmd=FAKE)
    assert len(killed) == 1
