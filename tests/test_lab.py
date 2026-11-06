import shutil
from pathlib import Path

import pytest
import yaml

from scoring.lab import LabNotFound, load_lab

LABS = Path(__file__).parent / "fixtures" / "labs"


def test_loads_all_fields():
    lab = load_lab("labx", LABS)
    assert lab.id == "labx"
    assert lab.root == LABS / "labx-sample"
    assert lab.title == "Sample lab"
    assert lab.agent_name == "sample-agent"
    assert lab.task_prompt == "Find the bug."
    assert lab.fixture == lab.root / "fixture"
    assert (lab.expected.file, lab.expected.line) == ("a.py", 1)
    assert lab.expected.cause == "Wrong value"
    assert lab.expected.fix == "Change x"
    assert lab.line_tolerance == 2
    assert lab.time_budget_s == 60
    assert lab.timeout_s == 120
    assert lab.consistency_runs == 3
    assert lab.weights["speed"] == 0.25


def test_prefix_match():
    assert load_lab("labx-sample", LABS).id == "labx"


def test_unknown_raises_with_available():
    with pytest.raises(LabNotFound) as e:
        load_lab("nope", LABS)
    assert "labx-sample" in str(e.value)


def test_variant_inherits_cause_fix():
    v = load_lab("labx", LABS).variants[0]
    assert v.name == "inherit"
    assert v.overlay is None
    assert v.remove == []
    assert v.expected.line == 2
    assert v.expected.cause == "Wrong value"
    assert v.expected.fix == "Change x"


def test_variant_overlay_resolved(tmp_path):
    root = tmp_path / "labx-sample"
    shutil.copytree(LABS / "labx-sample", root)
    data = yaml.safe_load((root / "lab.yaml").read_text())
    data["variants"][0]["overlay"] = "ov"
    data["variants"][0]["remove"] = ["a.py"]
    (root / "lab.yaml").write_text(yaml.safe_dump(data))
    v = load_lab("labx", tmp_path).variants[0]
    assert v.overlay == root / "ov"
    assert v.remove == ["a.py"]


def test_missing_key_raises(tmp_path):
    root = tmp_path / "labx-sample"
    shutil.copytree(LABS / "labx-sample", root)
    data = yaml.safe_load((root / "lab.yaml").read_text())
    del data["timeout_s"]
    (root / "lab.yaml").write_text(yaml.safe_dump(data))
    with pytest.raises(ValueError, match="timeout_s"):
        load_lab("labx", tmp_path)
