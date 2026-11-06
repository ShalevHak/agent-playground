from pathlib import Path

import pytest

from scoring.lab import load_lab
from scoring.workspace import build_workspace, changed_files, snapshot

LABS = Path(__file__).parent / "fixtures" / "labs"


@pytest.fixture
def lab():
    return load_lab("labx", LABS)


@pytest.fixture
def agent(tmp_path):
    f = tmp_path / "agent-src.md"
    f.write_text("agent body", encoding="utf-8")
    return f


def test_plain_workspace(lab, agent, tmp_path):
    ws = build_workspace(lab, None, agent, parent=tmp_path)
    assert ws.parent == tmp_path and ws.name.startswith("pg-")
    assert (ws / "a.py").read_text() == (lab.fixture / "a.py").read_text()
    assert (ws / "old.txt").exists()
    assert (ws / ".claude" / "agents" / "sample-agent.md").read_text() == "agent body"


def test_variant_overlay_and_remove(lab, agent, tmp_path):
    v = [x for x in lab.variants if x.name == "v1"][0]
    ws = build_workspace(lab, v, agent, parent=tmp_path)
    assert (ws / "b.py").read_text() == "new\n"
    assert "overlay" in (ws / "a.py").read_text()
    assert not (ws / "old.txt").exists()
    assert (ws / ".claude" / "agents" / "sample-agent.md").exists()


def test_fixture_untouched(lab, agent, tmp_path):
    v = [x for x in lab.variants if x.name == "v1"][0]
    before = snapshot(lab.fixture)
    build_workspace(lab, v, agent, parent=tmp_path)
    assert snapshot(lab.fixture) == before


def test_remove_missing_raises(lab, agent, tmp_path):
    v = [x for x in lab.variants if x.name == "v1"][0]
    v.remove = ["nope.txt"]
    with pytest.raises(FileNotFoundError, match="nope.txt"):
        build_workspace(lab, v, agent, parent=tmp_path)


def test_snapshot_skips_claude_and_uses_posix(lab, agent, tmp_path):
    ws = build_workspace(lab, None, agent, parent=tmp_path)
    (ws / "sub").mkdir()
    (ws / "sub" / "c.txt").write_text("c")
    snap = snapshot(ws)
    assert set(snap) == {"a.py", "old.txt", "sub/c.txt"}
    assert all(len(h) == 64 for h in snap.values())


def test_changed_files():
    before = {"a": "1", "b": "2", "c": "3"}
    after = {"a": "1", "b": "9", "d": "4"}
    assert changed_files(before, after) == ["b", "c", "d"]
    assert changed_files(before, before) == []
