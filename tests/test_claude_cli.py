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
