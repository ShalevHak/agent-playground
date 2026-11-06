import shutil
from pathlib import Path

import pytest

from scoring.lab import load_lab
from scoring.workspace import build_workspace

NEEDLE = "> BULK_THRESHOLD"
lab = load_lab("lab01")
SOLUTION = lab.root / "solution" / "bug-hunter.md"
CASES = [("base", None, lab.expected)] + [(v.name, v, v.expected) for v in lab.variants]


@pytest.fixture(params=CASES, ids=[c[0] for c in CASES])
def case(request, tmp_path):
    name, variant, expected = request.param
    ws = build_workspace(lab, variant, SOLUTION, parent=tmp_path)
    yield name, ws, expected
    shutil.rmtree(str(ws), ignore_errors=True)


def test_expected_line_holds_the_bug(case):
    _, ws, exp = case
    lines = (ws / exp.file).read_text(encoding="utf-8").splitlines()
    assert NEEDLE in lines[exp.line - 1]


def test_bug_appears_exactly_once(case):
    _, ws, _ = case
    hits = [p for p in ws.rglob("*.py") if NEEDLE in p.read_text(encoding="utf-8")]
    assert len(hits) == 1
    assert hits[0].read_text(encoding="utf-8").count(NEEDLE) == 1


def test_moved_bug_is_far_enough_from_base():
    moved = [v for v in lab.variants if v.name == "moved"][0]
    assert moved.expected.line - lab.expected.line >= 8


def test_renamed_has_no_pricing_module(tmp_path):
    v = [v for v in lab.variants if v.name == "renamed"][0]
    ws = build_workspace(lab, v, SOLUTION, parent=tmp_path)
    assert not (ws / "shop" / "pricing.py").exists()
    assert (ws / "shop" / "rates.py").exists()


def test_decoy_has_legacy_module(tmp_path):
    v = [v for v in lab.variants if v.name == "decoy"][0]
    ws = build_workspace(lab, v, SOLUTION, parent=tmp_path)
    assert (ws / "shop" / "legacy_pricing.py").exists()
    assert "FIXME: discount math looks wrong" in (ws / "shop" / "legacy_pricing.py").read_text()


def test_solution_agent_frontmatter():
    text = SOLUTION.read_text(encoding="utf-8")
    assert text.startswith("---\nname: bug-hunter\n")
    assert "tools: Read, Grep, Glob" in text
