"""Live calibration against the real claude CLI (costs tokens).

Run with: python -m pytest -m live -s
Proves the scorer discriminates: reference solution >= 90, sloppy agent <= 50.
"""
import json
from pathlib import Path

import pytest

from scoring.lab import REPO_ROOT
from scoring.run import main

SOLUTION = REPO_ROOT / "labs" / "lab01-contract" / "solution" / "bug-hunter.md"
SLOPPY = REPO_ROOT / "tests" / "agents" / "sloppy.md"


def _total(agent_file: Path, tmp_path: Path) -> dict:
    main(["lab01", "--agent-file", str(agent_file), "--runs-dir", str(tmp_path)])
    reports = list(tmp_path.glob("*/report.json"))
    assert len(reports) == 1
    return json.loads(reports[0].read_text(encoding="utf-8"))


@pytest.mark.live
def test_reference_solution_scores_high(tmp_path):
    report = _total(SOLUTION, tmp_path)
    print(json.dumps(report["scorecard"], indent=2))
    assert report["scorecard"]["total"] >= 90


@pytest.mark.live
def test_sloppy_agent_scores_low(tmp_path):
    report = _total(SLOPPY, tmp_path)
    print(json.dumps(report["scorecard"], indent=2))
    assert report["scorecard"]["total"] <= 50
